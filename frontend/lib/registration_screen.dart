import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'api_service.dart';

enum RegistrationRole { client, doctor, guardian }

class RegistrationScreen extends StatefulWidget {
  final VoidCallback onRegistered;

  const RegistrationScreen({super.key, required this.onRegistered});

  @override
  State<RegistrationScreen> createState() => _RegistrationScreenState();
}

class _RegistrationScreenState extends State<RegistrationScreen> {
  final _formKey = GlobalKey<FormState>();
  final _api = ApiService();

  final _nameController = TextEditingController();
  final _registrationNumberController = TextEditingController();
  final _licensingAuthorityController = TextEditingController();
  final _specializationController = TextEditingController();

  RegistrationRole _role = RegistrationRole.client;
  DateTime? _dateOfBirth;
  bool _isSubmitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _nameController.dispose();
    _registrationNumberController.dispose();
    _licensingAuthorityController.dispose();
    _specializationController.dispose();
    super.dispose();
  }

  String _formatDate(DateTime date) {
    final year = date.year.toString().padLeft(4, '0');
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }

  int _calculateAge(DateTime birthDate, DateTime today) {
    var age = today.year - birthDate.year;

    if (today.month < birthDate.month ||
        (today.month == birthDate.month && today.day < birthDate.day)) {
      age--;
    }

    return age;
  }

  Future<void> _chooseDateOfBirth() async {
    final today = DateTime.now();
    final initialDate = DateTime(today.year - 21, today.month, today.day);

    final selected = await showDatePicker(
      context: context,
      initialDate: _dateOfBirth ?? initialDate,
      firstDate: DateTime(today.year - 31),
      lastDate: today,
      helpText: 'Select your date of birth',
    );

    if (!mounted || selected == null) return;

    setState(() {
      _dateOfBirth = selected;
      _errorMessage = null;
    });
  }

  Future<void> _submitRegistration() async {
    if (_isSubmitting) return;

    if (!_formKey.currentState!.validate()) return;

    if (_role == RegistrationRole.client) {
      if (_dateOfBirth == null) {
        setState(() {
          _errorMessage = 'Please select your date of birth.';
        });
        return;
      }

      final age = _calculateAge(_dateOfBirth!, DateTime.now());

      if (age < 18 || age > 30) {
        setState(() {
          _errorMessage =
              'Client registration is currently available '
              'for adults aged 18 to 30.';
        });
        return;
      }
    }

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      switch (_role) {
        case RegistrationRole.client:
          await _api.registerClient(
            displayName: _nameController.text,
            dateOfBirth: _formatDate(_dateOfBirth!),
          );
          break;

        case RegistrationRole.doctor:
          await _api.registerDoctor(
            displayName: _nameController.text,
            registrationNumber: _registrationNumberController.text,
            licensingAuthority: _licensingAuthorityController.text,
            specialization: _specializationController.text,
          );
          break;

        case RegistrationRole.guardian:
          await _api.registerGuardian(displayName: _nameController.text);
          break;
      }

      if (!mounted) return;
      widget.onRegistered();
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _errorMessage = error.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  Widget _requiredField({
    required TextEditingController controller,
    required String label,
    IconData? icon,
  }) {
    return TextFormField(
      controller: controller,
      enabled: !_isSubmitting,
      textCapitalization: TextCapitalization.words,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: icon == null ? null : Icon(icon),
        border: const OutlineInputBorder(),
      ),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return 'Please enter $label.';
        }
        return null;
      },
    );
  }

  Widget _roleOption({
    required RegistrationRole role,
    required String title,
    required String description,
    required IconData icon,
  }) {
    final selected = _role == role;

    return Card(
      color: selected
          ? const Color(0xFFEDE7F6)
          : Theme.of(context).colorScheme.surface,
      child: RadioListTile<RegistrationRole>(
        value: role,
        enabled: !_isSubmitting,
        title: Row(
          children: [
            Icon(icon, color: const Color(0xFF6750A4)),
            const SizedBox(width: 10),
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
        subtitle: Text(description),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Join Voca Mind'),
        actions: [
          IconButton(
            tooltip: 'Logout',
            onPressed: _isSubmitting
                ? null
                : () => FirebaseAuth.instance.signOut(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(22),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Icon(
                    Icons.psychology_outlined,
                    size: 68,
                    color: Color(0xFF6750A4),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Welcome to Voca Mind',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'Choose how you would like to use Voca Mind.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 26),

                  RadioGroup<RegistrationRole>(
                    groupValue: _role,
                    onChanged: (value) {
                      if (value == null || _isSubmitting) return;

                      setState(() {
                        _role = value;
                        _errorMessage = null;
                      });
                    },
                    child: Column(
                      children: [
                        _roleOption(
                          role: RegistrationRole.client,
                          title: 'Client',
                          description:
                              'A private space to talk with your AI companion.',
                          icon: Icons.favorite_outline,
                        ),
                        _roleOption(
                          role: RegistrationRole.doctor,
                          title: 'Doctor',
                          description:
                              'Apply as a mental health professional. '
                              'Verification is required.',
                          icon: Icons.medical_services_outlined,
                        ),
                        _roleOption(
                          role: RegistrationRole.guardian,
                          title: 'Guardian',
                          description:
                              'Receive limited wellbeing updates only '
                              'with Client authorization.',
                          icon: Icons.shield_outlined,
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  _requiredField(
                    controller: _nameController,
                    label: 'Display name',
                    icon: Icons.person_outline,
                  ),

                  if (_role == RegistrationRole.client) ...[
                    const SizedBox(height: 18),
                    OutlinedButton.icon(
                      onPressed: _isSubmitting ? null : _chooseDateOfBirth,
                      icon: const Icon(Icons.calendar_month_outlined),
                      label: Text(
                        _dateOfBirth == null
                            ? 'Select date of birth'
                            : 'Date of birth: ${_formatDate(_dateOfBirth!)}',
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Client registration is available for ages 18–30.',
                      style: TextStyle(color: Colors.grey),
                    ),
                  ],

                  if (_role == RegistrationRole.doctor) ...[
                    const SizedBox(height: 18),
                    _requiredField(
                      controller: _registrationNumberController,
                      label: 'Professional registration number',
                    ),
                    const SizedBox(height: 18),
                    _requiredField(
                      controller: _licensingAuthorityController,
                      label: 'Licensing authority',
                    ),
                    const SizedBox(height: 18),
                    _requiredField(
                      controller: _specializationController,
                      label: 'Specialization',
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Professional privileges will remain disabled '
                      'until your credentials are reviewed and approved.',
                      style: TextStyle(color: Colors.grey),
                    ),
                  ],

                  if (_role == RegistrationRole.guardian) ...[
                    const SizedBox(height: 14),
                    const Text(
                      'Guardian registration does not provide access '
                      'to anyone’s private conversations. '
                      'Client authorization is required for '
                      'future wellbeing updates.',
                      style: TextStyle(color: Colors.grey),
                    ),
                  ],

                  if (_errorMessage != null) ...[
                    const SizedBox(height: 18),
                    Text(
                      _errorMessage!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],

                  const SizedBox(height: 26),

                  SizedBox(
                    height: 54,
                    child: FilledButton(
                      onPressed: _isSubmitting ? null : _submitRegistration,
                      child: _isSubmitting
                          ? const SizedBox(
                              height: 22,
                              width: 22,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Complete registration'),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
