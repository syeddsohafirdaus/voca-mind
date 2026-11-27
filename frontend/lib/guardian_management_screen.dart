import 'package:flutter/material.dart';

import 'guardian_api.dart';

class GuardianManagementScreen extends StatefulWidget {
  const GuardianManagementScreen({super.key});

  @override
  State<GuardianManagementScreen> createState() =>
      _GuardianManagementScreenState();
}

class _GuardianManagementScreenState extends State<GuardianManagementScreen> {
  final GuardianApi _api = GuardianApi();
  final TextEditingController _idController = TextEditingController();

  List<Map<String, dynamic>> _items = [];
  bool _busy = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    if (!mounted) return;

    setState(() {
      _busy = true;
      _error = null;
      _items = [];
    });

    try {
      final items = await _api.getAuthorizations();

      if (!mounted) return;

      setState(() {
        _items = items;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _busy = false;
        _error = e.toString();
      });
    }
  }

  Future<bool> _confirm(String title, String message) async {
    return await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: Text(title),
            content: Text(message),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Confirm'),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<void> _perform(Future<void> Function() action, String success) async {
    if (_busy || !mounted) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await action();

      if (!mounted) return;

      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(success)));

      await _refresh();
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _busy = false;
        _items = [];
        _error = '$e Refresh before trying again.';
      });
    }
  }

  Future<void> _addGuardian() async {
    final id = _idController.text.trim();

    final valid = RegExp(
      r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-'
      r'[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
      r'[0-9a-fA-F]{12}$',
    ).hasMatch(id);

    if (!valid) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Enter a valid Guardian ID.')),
      );
      return;
    }

    final confirmed = await _confirm(
      'Authorize Guardian?',
      'Guardian ID: $id\n\n'
          'Only continue if you obtained this ID directly '
          'from someone you trust and verified it with them.\n\n'
          'This guardian will see your display name and '
          'wellbeing updates you explicitly share. '
          'Your private AI conversations are not shared. '
          'You can revoke access at any time.',
    );

    if (!confirmed || !mounted) return;

    await _perform(() async {
      await _api.grant(guardianId: id, consent: true);

      if (mounted) _idController.clear();
    }, 'Guardian authorized.');
  }

  Future<void> _share(
    Map<String, dynamic> item,
    String wellbeing,
    String label,
  ) async {
    final id = item['id'] as String;
    final version = item['consent_version'] as String;
    final name = item['guardian_display_name'] ?? 'Guardian';

    final confirmed = await _confirm(
      'Share wellbeing update?',
      'Share "$label" with $name?\n\n'
          'This replaces your previous shared update. '
          'No private conversation will be included.',
    );

    if (!confirmed || !mounted) return;

    await _perform(
      () => _api.shareWellbeing(
        authorizationId: id,
        consentVersion: version,
        wellbeing: wellbeing,
        consent: true,
      ),
      'Wellbeing update shared.',
    );
  }

  Future<void> _withdraw(Map<String, dynamic> item) async {
    final id = item['id'] as String;
    final version = item['consent_version'] as String;

    final confirmed = await _confirm(
      'Withdraw wellbeing update?',
      'Your current wellbeing update will be removed '
          'from this guardian dashboard. Authorization '
          'will remain active.',
    );

    if (!confirmed || !mounted) return;

    await _perform(
      () =>
          _api.withdrawWellbeing(authorizationId: id, consentVersion: version),
      'Wellbeing update withdrawn.',
    );
  }

  Future<void> _revoke(Map<String, dynamic> item) async {
    final id = item['id'] as String;
    final version = item['consent_version'] as String;

    final confirmed = await _confirm(
      'Revoke guardian access?',
      'This guardian will lose access to your wellbeing '
          'updates and active connection. Information '
          'already seen cannot be recalled.',
    );

    if (!confirmed || !mounted) return;

    await _perform(
      () => _api.revoke(authorizationId: id, consentVersion: version),
      'Guardian access revoked.',
    );
  }

  Widget _guardianCard(Map<String, dynamic> item) {
    final active = item['status'] == 'active';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              item['guardian_display_name']?.toString() ?? 'Guardian',
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            Text(
              active ? 'Authorization active' : 'Access revoked',
              style: TextStyle(color: active ? Colors.green : Colors.grey),
            ),
            const SizedBox(height: 8),
            SelectableText(
              item['guardian_id']?.toString() ?? '',
              style: const TextStyle(fontSize: 12),
            ),
            if (active) ...[
              const Divider(),
              const Text('Share a wellbeing update'),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _share(item, 'doing_well', 'Doing well'),
                    child: const Text('Doing well'),
                  ),
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _share(item, 'managing', 'Managing'),
                    child: const Text('Managing'),
                  ),
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _share(
                            item,
                            'would_like_support',
                            'Would like support',
                          ),
                    child: const Text('Would like support'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: _busy ? null : () => _withdraw(item),
                icon: const Icon(Icons.visibility_off),
                label: const Text('Withdraw update'),
              ),
              TextButton.icon(
                onPressed: _busy ? null : () => _revoke(item),
                icon: const Icon(
                  Icons.person_remove_outlined,
                  color: Colors.red,
                ),
                label: const Text(
                  'Revoke access',
                  style: TextStyle(color: Colors.red),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _idController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Guardian Management'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _busy ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Icon(Icons.shield_outlined, size: 65, color: Color(0xFF6750A4)),
          const SizedBox(height: 16),
          const Text(
            'You control what you share',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          const Text(
            'Connecting a guardian is optional. '
            'Your private AI conversations are not '
            'shared with guardians.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _idController,
            enabled: !_busy && _error == null,
            decoration: const InputDecoration(
              labelText: 'Guardian ID',
              hintText: 'Paste Guardian ID',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.person_add_outlined),
            ),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: _busy || _error != null ? null : _addGuardian,
            icon: const Icon(Icons.person_add),
            label: const Text('Authorize Guardian'),
          ),
          const SizedBox(height: 24),
          const Text(
            'Your guardians',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          if (_busy)
            const Center(child: CircularProgressIndicator())
          else if (_error != null) ...[
            Text(_error!),
            TextButton(onPressed: _refresh, child: const Text('Refresh')),
          ] else if (_items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Text('No guardians connected.'),
              ),
            )
          else
            ..._items.map(_guardianCard),
        ],
      ),
    );
  }
}
