
import 'package:flutter/material.dart';
import 'api_service.dart';

class ChatHistoryScreen extends StatefulWidget {
  const ChatHistoryScreen({super.key});

  @override
  State<ChatHistoryScreen> createState() =>
      _ChatHistoryScreenState();
}

class _ChatHistoryScreenState extends State<ChatHistoryScreen> {
  final ApiService _api = ApiService();

  List<Map<String, dynamic>> _conversations = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadConversations();
  }

  Future<void> _loadConversations() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final conversations = await _api.getConversations();

      if (!mounted) return;

      setState(() {
        _conversations = conversations;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  String _getConversationTitle(Map<String, dynamic> conversation) {
    final messages = conversation['messages'];

    if (messages is List) {
      for (final item in messages) {
        if (item is Map && item['role'] == 'user') {
          final content = item['content']?.toString().trim() ?? '';

          if (content.isNotEmpty) {
            return content.length > 50
                ? '${content.substring(0, 50)}...'
                : content;
          }
        }
      }
    }

    return 'New Conversation';
  }

  String _getConversationDate(Map<String, dynamic> conversation) {
    final value = conversation['started_at'];

    if (value == null) return '';

    final date = DateTime.tryParse(value.toString());

    if (date == null) return '';

    final local = date.toLocal();

    return '${local.day}/${local.month}/${local.year}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chat History'),
        backgroundColor: const Color(0xFF6750A4),
        foregroundColor: Colors.white,
      ),
      body: _isLoading
          ? const Center(
              child: CircularProgressIndicator(),
            )
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.error_outline,
                          size: 48,
                          color: Colors.red,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          _error!,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadConversations,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _conversations.isEmpty
                  ? const Center(
                      child: Text(
                        'No previous conversations yet.',
                        style: TextStyle(fontSize: 17),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _loadConversations,
                      child: ListView.separated(
                        itemCount: _conversations.length,
                        separatorBuilder: (_, _) =>
                            const Divider(height: 1),
                        itemBuilder: (context, index) {
                          final conversation =
                              _conversations[index];

                          final id = conversation['id']?.toString();

                          return ListTile(
                            leading: const CircleAvatar(
                              backgroundColor: Color(0xFFEDE7F6),
                              child: Icon(
                                Icons.chat_bubble_outline,
                                color: Color(0xFF6750A4),
                              ),
                            ),
                            title: Text(
                              _getConversationTitle(conversation),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              _getConversationDate(conversation),
                            ),
                            trailing: const Icon(
                              Icons.chevron_right,
                            ),
                            onTap: id == null
                                ? null
                                : () {
                                    Navigator.pop(context, id);
                                  },
                          );
                        },
                      ),
                    ),
    );
  }
}
