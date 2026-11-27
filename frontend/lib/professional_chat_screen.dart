import 'package:flutter/material.dart';

import 'professional_api.dart';

class ProfessionalChatScreen extends StatefulWidget {
  final String assignmentId;
  final String role;

  const ProfessionalChatScreen({
    super.key,
    required this.assignmentId,
    required this.role,
  });

  @override
  State<ProfessionalChatScreen> createState() => _ProfessionalChatScreenState();
}

class _ProfessionalChatScreenState extends State<ProfessionalChatScreen> {
  final api = ProfessionalApi();
  final controller = TextEditingController();

  List<Map<String, dynamic>> messages = [];
  bool busy = false;
  bool available = false;
  String? error;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() async {
    if (busy) return;

    setState(() {
      busy = true;
      error = null;
      available = false;
    });

    try {
      final result = await api.messages(widget.assignmentId);

      if (!mounted) return;

      setState(() {
        messages = result;
        available = true;
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          messages = [];
          error = 'Messaging unavailable. Refresh to check access.';
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> send() async {
    final content = controller.text.trim();
    if (content.isEmpty || busy || !available) return;

    setState(() => busy = true);

    try {
      await api.sendMessage(widget.assignmentId, content);
      if (!mounted) return;
      controller.clear();
    } catch (_) {
      if (mounted) {
        setState(() {
          error = 'Delivery could not be confirmed. Refresh before retrying.';
          available = false;
          messages = [];
        });
      }
      return;
    } finally {
      if (mounted) setState(() => busy = false);
    }

    if (mounted) await refresh();
  }

  Future<void> markRead(String id) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await api.readMessage(widget.assignmentId, id);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to mark message read.')),
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
    if (mounted) await refresh();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Professional messaging'),
        actions: [
          IconButton(
            onPressed: busy ? null : refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.all(12),
              child: Text(
                'Messages are separate from AI conversations. '
                'Replies are not guaranteed immediately. '
                'This is not an emergency service.',
              ),
            ),
            if (busy) const LinearProgressIndicator(),
            if (error != null)
              Padding(padding: const EdgeInsets.all(12), child: Text(error!)),
            Expanded(
              child: ListView.builder(
                reverse: true,
                padding: const EdgeInsets.all(12),
                itemCount: messages.length,
                itemBuilder: (context, index) {
                  final item = messages[index];
                  final own = item['sender_role'] == widget.role;

                  return Align(
                    alignment: own
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              own ? 'You' : 'Other participant',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(item['content']?.toString() ?? ''),
                            if (!own && item['read_at'] == null)
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => markRead(item['id'].toString()),
                                child: const Text('Mark read'),
                              ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: controller,
                      enabled: available && !busy,
                      maxLength: 5000,
                      minLines: 1,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        hintText: 'Write a message',
                        counterText: '',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: busy || !available ? null : send,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
