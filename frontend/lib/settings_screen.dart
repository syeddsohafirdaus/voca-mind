
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'voice_preferences.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _isLoading = true;
  bool _voiceEnabled = true;
  double _speechSpeed = 0.48;
  String _language = 'en-IN';

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    try {
      final enabled = await VoicePreferences.getVoiceEnabled();
      final speed = await VoicePreferences.getSpeechSpeed();
      final language = await VoicePreferences.getLanguage();

      if (!mounted) return;

      setState(() {
        _voiceEnabled = enabled;
        _speechSpeed = speed;
        _language = language;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() => _isLoading = false);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to load voice settings: $e')),
      );
    }
  }

  Future<void> _updateVoiceEnabled(bool value) async {
    setState(() => _voiceEnabled = value);

    try {
      await VoicePreferences.setVoiceEnabled(value);
    } catch (e) {
      if (!mounted) return;
      setState(() => _voiceEnabled = !value);
      _showError(e);
    }
  }

  Future<void> _updateSpeechSpeed(double value) async {
    final previous = _speechSpeed;
    setState(() => _speechSpeed = value);

    try {
      await VoicePreferences.setSpeechSpeed(value);
    } catch (e) {
      if (!mounted) return;
      setState(() => _speechSpeed = previous);
      _showError(e);
    }
  }

  Future<void> _updateLanguage(String? value) async {
    if (value == null) return;

    final previous = _language;
    setState(() => _language = value);

    try {
      await VoicePreferences.setLanguage(value);
    } catch (e) {
      if (!mounted) return;
      setState(() => _language = previous);
      _showError(e);
    }
  }

  void _showError(Object error) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Unable to save setting: $error')),
    );
  }

  Future<void> _logout() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Logout'),
        content: const Text(
          'Are you sure you want to log out of Voca Mind?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirm != true || !mounted) return;

    try {
      await FirebaseAuth.instance.signOut();

      if (!mounted) return;

      Navigator.popUntil(context, (route) => route.isFirst);
    } catch (e) {
      if (mounted) _showError(e);
    }
  }

  String get _speedLabel {
    if (_speechSpeed <= 0.4) return 'Slow';
    if (_speechSpeed >= 0.6) return 'Fast';
    return 'Normal';
  }

  @override
  Widget build(BuildContext context) {
    final user = FirebaseAuth.instance.currentUser;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile & Settings'),
        backgroundColor: const Color(0xFF6750A4),
        foregroundColor: Colors.white,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const SizedBox(height: 16),

                const Center(
                  child: CircleAvatar(
                    radius: 46,
                    backgroundColor: Color(0xFFEDE7F6),
                    child: Icon(
                      Icons.person,
                      size: 52,
                      color: Color(0xFF6750A4),
                    ),
                  ),
                ),

                const SizedBox(height: 16),

                Center(
                  child: Text(
                    user?.displayName ?? 'Voca Mind User',
                    style: const TextStyle(
                      fontSize: 23,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),

                const SizedBox(height: 6),

                Center(
                  child: Text(
                    user?.email ?? 'No email available',
                    style: const TextStyle(color: Colors.grey),
                  ),
                ),

                const SizedBox(height: 30),

                const Text(
                  'ACCOUNT',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF6750A4),
                    letterSpacing: 1,
                  ),
                ),

                const SizedBox(height: 12),

                Card(
                  child: Column(
                    children: [
                      ListTile(
                        leading: const Icon(Icons.email_outlined),
                        title: const Text('Email Address'),
                        subtitle: Text(user?.email ?? 'Not available'),
                      ),
                      const Divider(height: 1),
                      ListTile(
                        leading: const Icon(Icons.verified_user_outlined),
                        title: const Text('Authentication'),
                        subtitle: const Text('Firebase Authentication'),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 25),

                const Text(
                  'VOICE ASSISTANT SETTINGS',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF6750A4),
                    letterSpacing: 1,
                  ),
                ),

                const SizedBox(height: 12),

                Card(
                  child: Column(
                    children: [
                      SwitchListTile(
                        secondary: const Icon(
                          Icons.volume_up_outlined,
                          color: Color(0xFF6750A4),
                        ),
                        title: const Text('Automatic Voice Responses'),
                        subtitle: const Text(
                          'Read assistant replies aloud',
                        ),
                        value: _voiceEnabled,
                        onChanged: _updateVoiceEnabled,
                      ),

                      const Divider(height: 1),

                      ListTile(
                        leading: const Icon(
                          Icons.speed,
                          color: Color(0xFF6750A4),
                        ),
                        title: const Text('Speech Speed'),
                        subtitle: Text(_speedLabel),
                      ),

                      Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                        ),
                        child: Slider(
                          min: 0.3,
                          max: 0.7,
                          divisions: 2,
                          value: _speechSpeed <= 0.4
                              ? 0.3
                              : _speechSpeed >= 0.6
                                  ? 0.7
                                  : 0.5,
                          label: _speedLabel,
                          onChanged: (value) {
                            setState(() => _speechSpeed = value);
                          },
                          onChangeEnd: _updateSpeechSpeed,
                        ),
                      ),

                      const Divider(height: 1),

                      ListTile(
                        leading: const Icon(
                          Icons.language,
                          color: Color(0xFF6750A4),
                        ),
                        title: const Text('Voice Language'),
                        subtitle: const Text(
                          'Choose the spoken language',
                        ),
                        trailing: DropdownButton<String>(
                          value: _language == 'en-US'
                              ? 'en-US'
                              : 'en-IN',
                          underline: const SizedBox.shrink(),
                          items: const [
                            DropdownMenuItem(
                              value: 'en-IN',
                              child: Text('English (India)'),
                            ),
                            DropdownMenuItem(
                              value: 'en-US',
                              child: Text('English (US)'),
                            ),
                          ],
                          onChanged: _updateLanguage,
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 25),

                const Text(
                  'ABOUT',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF6750A4),
                    letterSpacing: 1,
                  ),
                ),

                const SizedBox(height: 12),

                const Card(
                  child: ListTile(
                    leading: Icon(
                      Icons.psychology,
                      color: Color(0xFF6750A4),
                    ),
                    title: Text('Voca Mind AI'),
                    subtitle: Text(
                      'Your personal conversational assistant',
                    ),
                    trailing: Text('1.0.0'),
                  ),
                ),

                const SizedBox(height: 30),

                FilledButton.icon(
                  onPressed: _logout,
                  icon: const Icon(Icons.logout),
                  label: const Text('Logout'),
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.red,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 15),
                  ),
                ),

                const SizedBox(height: 20),
              ],
            ),
    );
  }
}
