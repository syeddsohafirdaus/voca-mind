import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'guardian_api.dart';

class GuardianDashboardScreen extends StatefulWidget {
  final String guardianId;

  const GuardianDashboardScreen({super.key, required this.guardianId});

  @override
  State<GuardianDashboardScreen> createState() =>
      _GuardianDashboardScreenState();
}

class _GuardianDashboardScreenState extends State<GuardianDashboardScreen> {
  final GuardianApi _api = GuardianApi();

  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    if (!mounted) return;

    setState(() {
      _loading = true;
      _error = null;
      _items = [];
    });

    try {
      final items = await _api.getDashboard();

      if (!mounted) return;

      setState(() {
        _items = items;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  String _label(dynamic value) {
    switch (value) {
      case 'doing_well':
        return 'Doing well';
      case 'managing':
        return 'Managing';
      case 'would_like_support':
        return 'Would like support';
      default:
        return 'No update shared';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Guardian Dashboard'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Logout',
            onPressed: () async {
              await FirebaseAuth.instance.signOut();
            },
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          children: [
            const Icon(
              Icons.shield_outlined,
              size: 64,
              color: Color(0xFF6750A4),
            ),
            const SizedBox(height: 16),
            const Text(
              'Connected with consent',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            const Text(
              'Only wellbeing updates deliberately shared by '
              'clients appear here. Private conversations '
              'are not accessible. This is not live monitoring.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            Card(
              child: ListTile(
                title: const Text('Your Guardian ID'),
                subtitle: SelectableText(widget.guardianId),
                trailing: IconButton(
                  tooltip: 'Copy Guardian ID',
                  icon: const Icon(Icons.copy),
                  onPressed: () async {
                    await Clipboard.setData(
                      ClipboardData(text: widget.guardianId),
                    );

                    if (!context.mounted) return;

                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Guardian ID copied')),
                    );
                  },
                ),
              ),
            ),
            const SizedBox(height: 20),
            if (_loading)
              const Center(child: CircularProgressIndicator())
            else if (_error != null)
              Column(
                children: [
                  Text(_error!),
                  TextButton(
                    onPressed: _refresh,
                    child: const Text('Try again'),
                  ),
                ],
              )
            else if (_items.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Text(
                    'No active client authorizations.',
                    textAlign: TextAlign.center,
                  ),
                ),
              )
            else
              ..._items.map(
                (item) => Card(
                  child: ListTile(
                    leading: const Icon(Icons.person_outline),
                    title: Text(
                      item['client_display_name']?.toString() ?? 'Client',
                    ),
                    subtitle: Text(
                      '${_label(item['wellbeing'])}\n'
                      '${item['shared_at'] ?? ''}',
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
