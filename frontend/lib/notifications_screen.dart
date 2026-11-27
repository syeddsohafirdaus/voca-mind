import 'package:flutter/material.dart';

import 'professional_api.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final api = ProfessionalApi();

  List<Map<String, dynamic>> items = [];
  bool busy = false;
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
    });

    try {
      final result = await api.notifications();
      if (mounted) setState(() => items = result);
    } catch (_) {
      if (mounted) {
        setState(() {
          items = [];
          error = 'Unable to load notifications.';
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> markRead(String id) async {
    if (busy) return;
    setState(() => busy = true);

    try {
      await api.readNotification(id);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to update notification.')),
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }

    if (mounted) await refresh();
  }

  String eventTitle(String event) {
    const labels = {
      'support_requested': 'Support request submitted',
      'assignment_proposed': 'Professional assignment proposed',
      'assignment_accepted': 'Assignment accepted',
      'assignment_revoked': 'Assignment revoked',
      'assignment_completed': 'Assignment completed',
      'professional_message': 'New professional message',
      'takeover_requested': 'Professional session requested',
      'takeover_accepted': 'Professional session accepted',
      'takeover_cancelled': 'Professional session cancelled',
      'takeover_ended': 'Professional session ended',
    };
    return labels[event] ?? 'Account update';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          IconButton(
            onPressed: busy ? null : refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          if (busy) const LinearProgressIndicator(),
          if (error != null) Text(error!),
          if (!busy && error == null && items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Text('No notifications yet.'),
            ),
          Expanded(
            child: ListView(
              children: items.map((item) {
                final unread = item['read_at'] == null;

                return ListTile(
                  leading: Icon(
                    unread
                        ? Icons.notifications_active
                        : Icons.notifications_none,
                  ),
                  title: Text(eventTitle(item['event_type'].toString())),
                  subtitle: Text(item['created_at']?.toString() ?? ''),
                  trailing: unread
                      ? TextButton(
                          onPressed: busy
                              ? null
                              : () => markRead(item['id'].toString()),
                          child: const Text('Mark read'),
                        )
                      : const Icon(Icons.check),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }
}
