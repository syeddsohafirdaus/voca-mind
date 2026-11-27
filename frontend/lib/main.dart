import 'professional_dashboard_screen.dart';

import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'firebase_options.dart';
import 'auth_screen.dart';
import 'api_service.dart';
import 'registration_screen.dart';
import 'chat_screen.dart';
import 'settings_screen.dart';
import 'guardian_dashboard_screen.dart';
import 'guardian_management_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  runApp(const VocaMindApp());
}

class VocaMindApp extends StatelessWidget {
  const VocaMindApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Voca Mind',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6750A4)),
        useMaterial3: true,
      ),
      home: const AuthGate(),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const LoadingScreen();
        }

        if (snapshot.hasError) {
          return const Scaffold(
            body: Center(child: Text('Unable to check authentication status.')),
          );
        }

        final user = snapshot.data;

        if (user == null) {
          return const AuthScreen();
        }

        return AccountGate(key: ValueKey(user.uid));
      },
    );
  }
}

class AccountGate extends StatefulWidget {
  const AccountGate({super.key});

  @override
  State<AccountGate> createState() => _AccountGateState();
}

class _AccountGateState extends State<AccountGate> {
  final ApiService _api = ApiService();

  late Future<Map<String, dynamic>?> _accountFuture;

  @override
  void initState() {
    super.initState();
    _refreshAccount();
  }

  void _refreshAccount() {
    _accountFuture = _api.getCurrentAccount();
  }

  void _retry() {
    setState(_refreshAccount);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>?>(
      future: _accountFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const LoadingScreen();
        }

        if (snapshot.hasError) {
          return AccountMessageScreen(
            title: 'Unable to load your account',
            message: snapshot.error.toString(),
            icon: Icons.error_outline,
            onRetry: _retry,
          );
        }

        final account = snapshot.data;

        if (account == null) {
          return RegistrationScreen(onRegistered: _retry);
        }

        final role = account['role']?.toString();
        final status = account['account_status']?.toString();
        final verified = account['is_verified'] == true;

        if (status == 'suspended') {
          return const AccountMessageScreen(
            title: 'Account unavailable',
            message:
                'Your Voca Mind account is currently suspended. '
                'Please contact platform support.',
            icon: Icons.lock_outline,
          );
        }

        if (role == 'client' && status == 'active') {
          return const HomeScreen();
        }

        if (role == 'doctor') {
          if (status == 'pending') {
            return const AccountMessageScreen(
              title: 'Verification pending',
              message:
                  'Your professional application has been submitted. '
                  'Voca Mind must verify your credentials before '
                  'professional features can be enabled.',
              icon: Icons.verified_user_outlined,
            );
          }

          if (status == 'active' && verified) {
            return const ProfessionalDashboardScreen(role: 'doctor');
          }

          return const AccountMessageScreen(
            title: 'Professional access unavailable',
            message:
                'Professional features require an active, '
                'verified account.',
            icon: Icons.lock_outline,
          );
        }

        if (role == 'guardian' && status == 'active') {
          final guardianId = account['id']?.toString();

          if (guardianId == null || guardianId.isEmpty) {
            return const AccountMessageScreen(
              title: 'Account unavailable',
              message: 'Guardian account identifier is missing.',
              icon: Icons.error_outline,
            );
          }

          return GuardianDashboardScreen(guardianId: guardianId);
        }

        return const AccountMessageScreen(
          title: 'Account access unavailable',
          message:
              'Your account cannot access this area. '
              'Please check your registration status.',
          icon: Icons.info_outline,
        );
      },
    );
  }
}

class LoadingScreen extends StatelessWidget {
  const LoadingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: CircularProgressIndicator()));
  }
}

class AccountMessageScreen extends StatelessWidget {
  final String title;
  final String message;
  final IconData icon;
  final VoidCallback? onRetry;

  const AccountMessageScreen({
    super.key,
    required this.title,
    required this.message,
    required this.icon,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Voca Mind'),
        actions: [
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await FirebaseAuth.instance.signOut();
            },
          ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 76, color: const Color(0xFF6750A4)),
              const SizedBox(height: 24),
              Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 25,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 14),
              Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 16),
              ),
              if (onRetry != null) ...[
                const SizedBox(height: 28),
                FilledButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Try again'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  Future<void> _signOut(BuildContext context) async {
    await FirebaseAuth.instance.signOut();
  }

  void _openSettings(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => const SettingsScreen()),
    );
  }

  void _openChat(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => const ChatScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = FirebaseAuth.instance.currentUser;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Voca Mind',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        actions: [
          IconButton(
            tooltip: 'Profile & Settings',
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => _openSettings(context),
          ),
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout),
            onPressed: () => _signOut(context),
          ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                height: 125,
                width: 125,
                decoration: BoxDecoration(
                  color: const Color(0xFFEDE7F6),
                  borderRadius: BorderRadius.circular(35),
                ),
                child: const Icon(
                  Icons.psychology,
                  size: 85,
                  color: Color(0xFF6750A4),
                ),
              ),
              const SizedBox(height: 28),
              const Text(
                'Welcome to Voca Mind!',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              Text(
                user?.email ?? 'Signed in successfully',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.grey, fontSize: 15),
              ),
              const SizedBox(height: 35),
              SizedBox(
                width: double.infinity,
                height: 55,
                child: FilledButton.icon(
                  onPressed: () => _openChat(context),
                  icon: const Icon(Icons.chat_bubble_outline),
                  label: const Text(
                    'Start AI Chat',
                    style: TextStyle(fontSize: 16),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                height: 55,
                child: OutlinedButton.icon(
                  onPressed: () => _openSettings(context),
                  icon: const Icon(Icons.person_outline),
                  label: const Text('Profile & Settings'),
                ),
              ),

              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                height: 55,
                child: OutlinedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => const GuardianManagementScreen(),
                    ),
                  ),
                  icon: const Icon(Icons.shield_outlined),
                  label: const Text('Guardian Management'),
                ),
              ),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                height: 55,
                child: OutlinedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          const ProfessionalDashboardScreen(role: 'client'),
                    ),
                  ),
                  icon: const Icon(Icons.medical_services_outlined),
                  label: const Text('Professional Support'),
                ),
              ),
              const SizedBox(height: 28),
              const Text(
                'Your personal AI conversational assistant',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey, fontSize: 14),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
