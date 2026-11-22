import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:flutter_tts/flutter_tts.dart';

import 'api_service.dart';
import 'chat_history_screen.dart';
import 'voice_preferences.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  final ApiService _api = ApiService();
  final stt.SpeechToText _speech = stt.SpeechToText();
  final FlutterTts _flutterTts = FlutterTts();

  final List<Map<String, String>> _messages = [];

  String? _conversationId;
  bool _isLoading = false;
  bool _isInitializing = true;
  bool _isListening = false;
  bool _isSpeaking = false;
  bool _speechReady = false;
  bool _voiceEnabled = true;
  double _speechSpeed = 0.48;
  String _voiceLanguage = 'en-IN';

  String? _error;

  @override
  void initState() {
    super.initState();

    _initializeVoice();
    _initializeConversation();
  }

  // ==========================================
  // TEXT TO SPEECH INITIALIZATION
  // ==========================================

  Future<void> _initializeVoice() async {
    try {
      final enabled = await VoicePreferences.getVoiceEnabled();
      final speed = await VoicePreferences.getSpeechSpeed();
      final language = await VoicePreferences.getLanguage();
      if (!mounted) return;
      setState(() {
        _voiceEnabled = enabled;
        _speechSpeed = speed;
        _voiceLanguage = language;
      });
    } catch (e) {
      debugPrint('Unable to load voice preferences: $e');
    }
    await _initializeTts();
  }

  Future<void> _initializeTts() async {
    try {
      await _flutterTts.setLanguage(_voiceLanguage);
      await _flutterTts.setSpeechRate(_speechSpeed);
      await _flutterTts.setPitch(1.0);
      await _flutterTts.setVolume(1.0);

      _flutterTts.setStartHandler(() {
        if (mounted) {
          setState(() => _isSpeaking = true);
        }
      });

      _flutterTts.setCompletionHandler(() {
        if (mounted) {
          setState(() => _isSpeaking = false);
        }
      });

      _flutterTts.setCancelHandler(() {
        if (mounted) {
          setState(() => _isSpeaking = false);
        }
      });

      _flutterTts.setErrorHandler((message) {
        if (mounted) {
          setState(() => _isSpeaking = false);
        }
      });
    } catch (e) {
      debugPrint('TTS initialization error: $e');
    }
  }

  Future<void> _speakText(String text) async {
    if (text.trim().isEmpty) return;

    try {
      await _flutterTts.stop();

      if (!mounted) return;
      await _flutterTts.setLanguage(_voiceLanguage);
      await _flutterTts.setSpeechRate(_speechSpeed);
      await _flutterTts.speak(text);
    } catch (e) {
      debugPrint('Speech error: $e');
    }
  }

  Future<void> _stopSpeaking() async {
    try {
      await _flutterTts.stop();
    } catch (e) {
      debugPrint('Unable to stop speech: $e');
    }

    if (mounted) {
      setState(() => _isSpeaking = false);
    }
  }

  Future<void> _toggleVoice() async {
    final enabled = !_voiceEnabled;
    if (!enabled) await _stopSpeaking();
    if (!mounted) return;
    setState(() => _voiceEnabled = enabled);
    try {
      await VoicePreferences.setVoiceEnabled(enabled);
    } catch (e) {
      debugPrint('Unable to save voice preference: $e');
    }
  }

  // ==========================================
  // CONVERSATION MANAGEMENT
  // ==========================================

  Future<void> _initializeConversation() async {
    if (_isInitializing && _conversationId != null) return;

    await _stopListening();
    await _stopSpeaking();

    if (!mounted) return;

    setState(() {
      _isInitializing = true;
      _error = null;
      _conversationId = null;
      _messages.clear();
      _controller.clear();
    });

    try {
      final id = await _api.createConversation();

      if (!mounted) return;

      setState(() {
        _conversationId = id;
        _isInitializing = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _isInitializing = false;
        _error = e.toString();
      });
    }
  }

  // Refresh the current conversation after a failed request.
  // Fetches saved messages instead of resending the previous POST.
  Future<void> _refreshConversation() async {
    final id = _conversationId;
    if (id == null || _isLoading || _isInitializing) return;

    setState(() {
      _isInitializing = true;
      _error = null;
    });

    try {
      final savedMessages = await _api.getMessages(id);
      if (!mounted || _conversationId != id) return;

      setState(() {
        _messages
          ..clear()
          ..addAll(
            savedMessages.map(
              (item) => {
                'role': item['role']?.toString() ?? '',
                'content': item['content']?.toString() ?? '',
              },
            ),
          );
        _isInitializing = false;
      });
      _scrollToBottom();

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Chat refreshed from saved history. '
            'If your last message is missing, it may not have been saved.',
          ),
          duration: Duration(seconds: 5),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isInitializing = false;
        _error = e.toString();
      });
    }
  }

  // Load an existing conversation.
  Future<void> _loadConversation(String conversationId) async {
    await _stopListening();
    await _stopSpeaking();

    if (!mounted) return;

    setState(() {
      _isInitializing = true;
      _error = null;
    });

    try {
      final savedMessages = await _api.getMessages(conversationId);

      if (!mounted) return;

      setState(() {
        _conversationId = conversationId;
        _controller.clear();

        _messages
          ..clear()
          ..addAll(
            savedMessages.map(
              (message) => {
                'role': message['role']?.toString() ?? '',
                'content': message['content']?.toString() ?? '',
              },
            ),
          );

        _isInitializing = false;
      });

      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _isInitializing = false;
        _error = e.toString();
      });
    }
  }

  // Open chat history.
  Future<void> _openHistory() async {
    if (_isLoading || _isInitializing) return;

    await _stopListening();
    await _stopSpeaking();

    if (!mounted) return;

    final selectedId = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (context) => const ChatHistoryScreen()),
    );

    if (!mounted || selectedId == null) return;

    await _loadConversation(selectedId);
  }

  // ==========================================
  // SPEECH TO TEXT
  // ==========================================

  Future<void> _startListening() async {
    if (_isLoading || _isInitializing || _conversationId == null) {
      return;
    }

    try {
      if (_isSpeaking) {
        await _stopSpeaking();
      }

      if (!_speechReady) {
        final available = await _speech.initialize(
          onStatus: (status) {
            if (!mounted) return;

            if (status == 'done' || status == 'notListening') {
              setState(() => _isListening = false);
            }
          },
          onError: (error) {
            if (!mounted) return;

            setState(() => _isListening = false);

            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Speech recognition error: ${error.errorMsg}'),
              ),
            );
          },
        );

        if (!mounted) return;

        if (!available) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Speech recognition is unavailable. '
                'Check microphone permission and Google speech services.',
              ),
            ),
          );
          return;
        }

        _speechReady = true;
      }

      await _speech.listen(
        onResult: (result) {
          if (!mounted) return;

          _controller.text = result.recognizedWords;

          _controller.selection = TextSelection.collapsed(
            offset: _controller.text.length,
          );

          if (result.finalResult) {
            setState(() => _isListening = false);
          }
        },
        listenOptions: stt.SpeechListenOptions(
          partialResults: true,
          cancelOnError: true,
        ),
      );

      if (!mounted) return;

      setState(() {
        _isListening = _speech.isListening;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() => _isListening = false);

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Unable to start microphone: $e')));
    }
  }

  Future<void> _stopListening() async {
    if (_speech.isListening) {
      await _speech.stop();
    }

    if (mounted) {
      setState(() => _isListening = false);
    }
  }

  Future<void> _toggleListening() async {
    if (_isListening) {
      await _stopListening();
    } else {
      await _startListening();
    }
  }

  // ==========================================
  // SEND MESSAGE
  // ==========================================

  Future<void> _sendMessage() async {
    if (_isListening) {
      await _stopListening();
    }

    final message = _controller.text.trim();

    if (message.isEmpty ||
        _isLoading ||
        _isInitializing ||
        _conversationId == null) {
      return;
    }

    await _stopSpeaking();

    if (!mounted) return;

    setState(() {
      _messages.add({'role': 'user', 'content': message});

      _isLoading = true;
      _error = null;
    });

    _controller.clear();
    _scrollToBottom();

    try {
      final reply = await _api.sendMessage(
        conversationId: _conversationId!,
        message: message,
      );

      if (!mounted) return;

      setState(() {
        _messages.add({'role': 'assistant', 'content': reply});

        _isLoading = false;
      });

      _scrollToBottom();

      // Automatically speak the assistant response.
      if (_voiceEnabled) {
        await _speakText(reply);
      }
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _isLoading = false;
        _error = e.toString();
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Message status is uncertain. '
            'Use Refresh Chat to check saved messages before sending again.',
          ),
          duration: Duration(seconds: 6),
        ),
      );
    }
  }

  // ==========================================
  // SCROLL MANAGEMENT
  // ==========================================

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scrollController.hasClients) return;

      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  // ==========================================
  // DISPOSE
  // ==========================================

  @override
  void dispose() {
    _speech.cancel();
    _flutterTts.stop();

    _controller.dispose();
    _scrollController.dispose();

    super.dispose();
  }

  // ==========================================
  // USER INTERFACE
  // ==========================================

  @override
  Widget build(BuildContext context) {
    final canInteract =
        !_isLoading && !_isInitializing && _conversationId != null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Voca Mind AI'),
        backgroundColor: const Color(0xFF6750A4),
        foregroundColor: Colors.white,
        actions: [
          // Enable or disable automatic voice.
          IconButton(
            tooltip: _voiceEnabled ? 'Disable voice' : 'Enable voice',
            onPressed: _toggleVoice,
            icon: Icon(_voiceEnabled ? Icons.volume_up : Icons.volume_off),
          ),

          // Stop current speech.
          if (_isSpeaking)
            IconButton(
              tooltip: 'Stop speaking',
              onPressed: _stopSpeaking,
              icon: const Icon(Icons.stop_circle_outlined),
            ),

          // Chat history.
          IconButton(
            tooltip: 'Chat History',
            onPressed: canInteract ? _openHistory : null,
            icon: const Icon(Icons.history),
          ),

          // New conversation.
          IconButton(
            tooltip: 'New Chat',
            onPressed: canInteract ? _initializeConversation : null,
            icon: const Icon(Icons.add_comment_outlined),
          ),
        ],
      ),

      body: Column(
        children: [
          if (_isInitializing) const LinearProgressIndicator(),

          // Error message.
          if (_error != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              color: Colors.red.shade50,
              child: Column(
                children: [
                  Text(_error!, style: const TextStyle(color: Colors.red)),

                  if (_conversationId == null)
                    TextButton(
                      onPressed: _isInitializing
                          ? null
                          : _initializeConversation,
                      child: const Text('Retry'),
                    )
                  else
                    TextButton.icon(
                      onPressed: (_isInitializing || _isLoading)
                          ? null
                          : _refreshConversation,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Refresh Chat'),
                    ),
                ],
              ),
            ),

          // Chat messages.
          Expanded(
            child: _messages.isEmpty
                ? const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.psychology,
                          size: 70,
                          color: Color(0xFF6750A4),
                        ),
                        SizedBox(height: 16),
                        Text(
                          'How can I help you today?',
                          style: TextStyle(fontSize: 20),
                        ),
                        SizedBox(height: 8),
                        Text(
                          'Type or speak to Voca Mind',
                          style: TextStyle(color: Colors.grey),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      final message = _messages[index];

                      final isUser = message['role'] == 'user';

                      final content = message['content'] ?? '';

                      return Align(
                        alignment: isUser
                            ? Alignment.centerRight
                            : Alignment.centerLeft,
                        child: Container(
                          margin: const EdgeInsets.symmetric(vertical: 6),
                          padding: const EdgeInsets.all(12),
                          constraints: BoxConstraints(
                            maxWidth: MediaQuery.of(context).size.width * 0.82,
                          ),
                          decoration: BoxDecoration(
                            color: isUser
                                ? const Color(0xFF6750A4)
                                : const Color(0xFFEDE7F6),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                content,
                                style: TextStyle(
                                  fontSize: 16,
                                  color: isUser ? Colors.white : Colors.black87,
                                ),
                              ),

                              // Replay assistant response.
                              if (!isUser && content.isNotEmpty)
                                Align(
                                  alignment: Alignment.centerRight,
                                  child: IconButton(
                                    tooltip: 'Read aloud',
                                    visualDensity: VisualDensity.compact,
                                    onPressed: () => _speakText(content),
                                    icon: const Icon(
                                      Icons.volume_up_outlined,
                                      color: Color(0xFF6750A4),
                                      size: 21,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),

          // Assistant loading indicator.
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  SizedBox(width: 10),
                  Text('Voca Mind is thinking...'),
                ],
              ),
            ),

          // Listening indicator.
          if (_isListening)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.mic, color: Colors.red, size: 18),
                  SizedBox(width: 6),
                  Text(
                    'Listening... Speak now',
                    style: TextStyle(color: Colors.red),
                  ),
                ],
              ),
            ),

          // Speaking indicator.
          if (_isSpeaking)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.volume_up, color: Color(0xFF6750A4), size: 18),
                  SizedBox(width: 6),
                  Text(
                    'Voca Mind is speaking...',
                    style: TextStyle(color: Color(0xFF6750A4)),
                  ),
                ],
              ),
            ),

          // Message input and controls.
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      enabled: canInteract && !_isListening,
                      decoration: InputDecoration(
                        hintText: _isListening
                            ? 'Listening...'
                            : 'Type or speak your message...',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                        ),
                      ),
                      onSubmitted: (_) => _sendMessage(),
                    ),
                  ),

                  const SizedBox(width: 6),

                  // Microphone button.
                  IconButton(
                    tooltip: _isListening
                        ? 'Stop listening'
                        : 'Start voice input',
                    onPressed: canInteract ? _toggleListening : null,
                    icon: Icon(
                      _isListening ? Icons.stop_circle : Icons.mic,
                      color: _isListening
                          ? Colors.red
                          : const Color(0xFF6750A4),
                    ),
                  ),

                  // Send button.
                  IconButton.filled(
                    onPressed: canInteract ? _sendMessage : null,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
