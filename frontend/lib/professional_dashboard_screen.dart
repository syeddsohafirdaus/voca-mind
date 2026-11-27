import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'professional_api.dart';
import 'professional_consent.dart';
import 'professional_chat_screen.dart';
import 'notifications_screen.dart';

class ProfessionalDashboardScreen extends StatefulWidget {
  final String role;

  const ProfessionalDashboardScreen({super.key, required this.role});

  @override
  State<ProfessionalDashboardScreen> createState() =>
      _ProfessionalDashboardScreenState();
}

class _ProfessionalDashboardScreenState
    extends State<ProfessionalDashboardScreen> {
  final api = ProfessionalApi();

  List<Map<String, dynamic>> assignments = [];
  List<Map<String, dynamic>> requests = [];
  List<Map<String, dynamic>> takeovers = [];

  bool busy = false;
  bool loaded = false;
  String? error;
  String? displayName;

  bool get isClient => widget.role == 'client';

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() async {
    if (busy) return;

    setState(() {
      busy = true;
      loaded = false;
      error = null;
    });

    try {
      String? name;

      if (!isClient) {
        final dashboard = await api.dashboard();

        if (dashboard['dashboard_access'] != true ||
            dashboard['is_verified'] != true) {
          throw Exception('Professional access unavailable.');
        }

        name = dashboard['display_name']?.toString();
      }

      final assignmentData = await api.assignments(widget.role);
      final takeoverData = await api.takeovers(widget.role);
      final requestData = isClient
          ? await api.supportRequests()
          : <Map<String, dynamic>>[];

      if (!mounted) return;

      setState(() {
        displayName = name;
        assignments = assignmentData;
        takeovers = takeoverData;
        requests = requestData;
        loaded = true;
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          assignments = [];
          requests = [];
          takeovers = [];
          error = 'Unable to load professional support. Please refresh.';
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> perform(
    String title,
    String explanation,
    Future<dynamic> Function() action,
  ) async {
    if (busy || !loaded) return;

    setState(() => busy = true);

    final confirmed = await confirmProfessionalAction(
      context,
      title,
      explanation,
    );

    if (!mounted) return;

    if (!confirmed) {
      setState(() => busy = false);
      return;
    }

    try {
      await action();

      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Action completed.')));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Action could not be confirmed. Refresh before retrying.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }

    if (mounted) await refresh();
  }

  Widget actionButton(
    String label,
    String explanation,
    Future<dynamic> Function() action,
  ) {
    return OutlinedButton(
      onPressed: busy || !loaded
          ? null
          : () => perform(label, explanation, action),
      child: Text(label),
    );
  }

  Widget assignmentCard(Map<String, dynamic> item) {
    final id = item['id'].toString();
    final status = item['status'].toString();

    final sessions = takeovers
        .where(
          (session) =>
              session['assignment_id'] == id &&
              ['requested', 'active'].contains(session['status']),
        )
        .toList();

    final session = sessions.isEmpty ? null : sessions.first;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              isClient ? 'Professional assignment' : 'Client assignment',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            SelectableText(
              '${isClient ? "Professional" : "Client"} ID: '
              '${item[isClient ? "doctor_id" : "client_id"]}',
            ),
            Text('Assignment status: $status'),
            const SizedBox(height: 8),

            if (isClient && status == 'pending')
              actionButton(
                'Accept assignment',
                'Accept this professional assignment and enable '
                    'separate professional messaging. Your AI conversation '
                    'history will not be shared.',
                () => api.assignmentAction(id, 'accept'),
              ),

            if (status == 'active') ...[
              FilledButton.icon(
                onPressed: busy || !loaded
                    ? null
                    : () async {
                        await Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => ProfessionalChatScreen(
                              assignmentId: id,
                              role: widget.role,
                            ),
                          ),
                        );
                        if (mounted) await refresh();
                      },
                icon: const Icon(Icons.chat_outlined),
                label: const Text('Professional messaging'),
              ),
              const Divider(),
              Text(
                'Professional session: '
                '${session?["status"] ?? "Not requested"}',
              ),

              if (isClient && session == null)
                actionButton(
                  'Request professional session',
                  'Request a professional-led session. If accepted, '
                      'ordinary AI replies will pause in eligible sessions. '
                      'AI messages are not forwarded automatically. '
                      'This does not guarantee immediate human assistance.',
                  () => api.requestTakeover(id),
                ),

              if (session != null && session['status'] == 'requested')
                actionButton(
                  isClient ? 'Cancel session request' : 'Accept session',
                  isClient
                      ? 'Cancel this pending session request.'
                      : 'Accept this session only if you can provide '
                            'appropriate professional support.',
                  () => api.takeoverAction(
                    id,
                    session['id'].toString(),
                    isClient ? 'cancel' : 'accept',
                  ),
                ),

              if (session != null && session['status'] == 'active')
                actionButton(
                  'End professional session',
                  'End this session and allow ordinary AI conversation '
                      'to resume.',
                  () => api.takeoverAction(id, session['id'].toString(), 'end'),
                ),
            ],

            if (isClient && ['pending', 'active'].contains(status))
              actionButton(
                'Revoke assignment',
                'Remove this assignment and close its professional '
                    'messaging and session access.',
                () => api.assignmentAction(id, 'revoke'),
              ),

            if (!isClient && status == 'active')
              actionButton(
                'Complete assignment',
                'Close this professional assignment and its messaging '
                    'and session access.',
                () => api.assignmentAction(id, 'complete'),
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final openRequest = requests.any(
      (item) => ['pending', 'assigned'].contains(item['status']),
    );

    final openAssignment = assignments.any(
      (item) => ['pending', 'active'].contains(item['status']),
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(
          isClient ? 'Professional support' : 'Professional dashboard',
        ),
        actions: [
          IconButton(
            tooltip: 'Notifications',
            onPressed: busy
                ? null
                : () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => const NotificationsScreen(),
                    ),
                  ),
            icon: const Icon(Icons.notifications_outlined),
          ),
          IconButton(
            tooltip: 'Refresh',
            onPressed: busy ? null : refresh,
            icon: const Icon(Icons.refresh),
          ),
          if (!isClient)
            IconButton(
              tooltip: 'Logout',
              onPressed: busy ? null : () => FirebaseAuth.instance.signOut(),
              icon: const Icon(Icons.logout),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (busy) const LinearProgressIndicator(),
          if (error != null) Text(error!),
          if (loaded) ...[
            if (!isClient)
              Text(
                'Welcome, ${displayName ?? "Professional"}',
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),

            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'Professional support is consent-based. '
                  'Private AI conversations are not automatically shared. '
                  'This service does not provide emergency response '
                  'or guaranteed immediate assistance.',
                ),
              ),
            ),

            if (isClient) ...[
              const Text(
                'Support requests',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),

              if (!openRequest && !openAssignment)
                actionButton(
                  'Request professional support',
                  'Submit a request for the platform to arrange '
                      'professional support. Your AI chat content is not '
                      'included in the request.',
                  api.requestSupport,
                ),

              if (requests.isEmpty) const Text('No support requests yet.'),

              ...requests.map(
                (item) => Card(
                  child: ListTile(
                    title: Text('Status: ${item["status"]}'),
                    subtitle: Text(item['created_at']?.toString() ?? ''),
                    trailing: item['status'] == 'pending'
                        ? TextButton(
                            onPressed: busy
                                ? null
                                : () => perform(
                                    'Cancel request',
                                    'Cancel this pending support request.',
                                    () => api.cancelSupport(
                                      item['id'].toString(),
                                    ),
                                  ),
                            child: const Text('Cancel'),
                          )
                        : null,
                  ),
                ),
              ),
            ],

            const SizedBox(height: 20),
            Text(
              'Assignments (${assignments.length})',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),

            if (assignments.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('No assignments available.'),
              ),

            ...assignments.map(assignmentCard),
          ],
        ],
      ),
    );
  }
}
