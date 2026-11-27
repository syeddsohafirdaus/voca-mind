import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;

class ApiService {
  Future<dynamic> requestJson(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? query,
  }) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);

    final response = await _handleRequest(() async {
      final headers = await _headers();

      switch (method) {
        case 'GET':
          return http.get(uri, headers: headers);
        case 'POST':
          return http.post(uri, headers: headers, body: jsonEncode(body ?? {}));
        case 'DELETE':
          return http.delete(uri, headers: headers);
        default:
          throw ArgumentError('Unsupported HTTP method');
      }
    }, timeout: const Duration(seconds: 30));

    _checkResponse(response);

    if (response.statusCode == 204 || response.body.isEmpty) {
      return null;
    }

    return jsonDecode(response.body);
  }

  // Android emulator connects to the Windows/WSL backend.
  static const String baseUrl = 'http://10.0.2.2:8000/api/v1';

  // ==========================================
  // FIREBASE AUTHENTICATION
  // ==========================================

  Future<Map<String, String>> _headers() async {
    final user = FirebaseAuth.instance.currentUser;

    if (user == null) {
      throw Exception('Please log in to continue.');
    }

    final token = await user.getIdToken();

    if (token == null || token.isEmpty) {
      throw Exception(
        'Unable to verify your login. '
        'Please sign in again.',
      );
    }

    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }

  // ==========================================
  // HTTP RESPONSE VALIDATION
  // ==========================================

  void _checkResponse(http.Response response) {
    final status = response.statusCode;

    if (status >= 200 && status < 300) {
      return;
    }

    if (status == 401) {
      throw Exception(
        'Your session may have expired. '
        'Please sign in again.',
      );
    }

    if (status == 403) {
      throw Exception('You do not have permission to access this resource.');
    }

    if (status == 404) {
      throw Exception('The requested resource could not be found.');
    }

    if (status == 409) {
      throw Exception(
        'This information has changed. Refresh and review '
        'your action before trying again.',
      );
    }

    if (status == 422) {
      throw Exception('Please check the information and consent requirements.');
    }

    if (status == 429) {
      throw Exception(
        'Too many requests. '
        'Please wait before trying again.',
      );
    }

    if (status >= 500) {
      throw Exception(
        'Voca Mind is temporarily unavailable. '
        'Please try again later.',
      );
    }

    throw Exception(
      'Unable to complete your request '
      '(HTTP $status).',
    );
  }

  // ==========================================
  // NETWORK ERROR HANDLING
  // ==========================================

  Future<http.Response> _handleRequest(
    Future<http.Response> Function() request, {
    required Duration timeout,
  }) async {
    try {
      return await request().timeout(timeout);
    } on TimeoutException {
      throw Exception(
        'The request took too long. '
        'Please check your connection and try again.',
      );
    } on SocketException {
      throw Exception(
        'Cannot connect to Voca Mind. '
        'Please check that the backend server '
        'is running.',
      );
    } on http.ClientException {
      throw Exception(
        'Network connection failed. '
        'Please check your connection '
        'and try again.',
      );
    }
  }

  // ==========================================
  // GET CURRENT VOCA MIND ACCOUNT
  // ==========================================

  Future<Map<String, dynamic>?> getCurrentAccount() async {
    final response = await _handleRequest(
      () async =>
          http.get(Uri.parse('$baseUrl/auth/me'), headers: await _headers()),
      timeout: const Duration(seconds: 20),
    );

    // A Firebase user without a Voca Mind registration
    // may receive HTTP 404 from the backend.
    if (response.statusCode == 404) {
      return null;
    }

    _checkResponse(response);

    final data = jsonDecode(response.body);

    if (data is! Map<String, dynamic>) {
      throw Exception('Invalid account information received.');
    }

    final role = data['role'];
    final accountStatus = data['account_status'];

    if (role is! String || accountStatus is! String) {
      throw Exception('Incomplete account information received.');
    }

    return data;
  }

  // ==========================================
  // REGISTER CLIENT
  // ==========================================

  Future<Map<String, dynamic>> registerClient({
    required String displayName,
    required String dateOfBirth,
  }) async {
    final response = await _handleRequest(
      () async => http.post(
        Uri.parse('$baseUrl/auth/register/client'),
        headers: await _headers(),
        body: jsonEncode({
          'display_name': displayName.trim(),
          'date_of_birth': dateOfBirth,
        }),
      ),
      timeout: const Duration(seconds: 20),
    );

    _checkResponse(response);

    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  // ==========================================
  // REGISTER GUARDIAN
  // ==========================================

  Future<Map<String, dynamic>> registerGuardian({
    required String displayName,
  }) async {
    final response = await _handleRequest(
      () async => http.post(
        Uri.parse('$baseUrl/auth/register/guardian'),
        headers: await _headers(),
        body: jsonEncode({'display_name': displayName.trim()}),
      ),
      timeout: const Duration(seconds: 20),
    );

    _checkResponse(response);

    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  // ==========================================
  // REGISTER DOCTOR APPLICATION
  // ==========================================

  Future<Map<String, dynamic>> registerDoctor({
    required String displayName,
    required String registrationNumber,
    required String licensingAuthority,
    required String specialization,
  }) async {
    final response = await _handleRequest(
      () async => http.post(
        Uri.parse('$baseUrl/auth/register/doctor'),
        headers: await _headers(),
        body: jsonEncode({
          'display_name': displayName.trim(),
          'registration_number': registrationNumber.trim(),
          'licensing_authority': licensingAuthority.trim(),
          'specialization': specialization.trim(),
        }),
      ),
      timeout: const Duration(seconds: 20),
    );

    _checkResponse(response);

    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  // ==========================================
  // CREATE NEW CONVERSATION
  // ==========================================

  Future<String> createConversation() async {
    final response = await _handleRequest(
      () async => http.post(
        Uri.parse('$baseUrl/conversations'),
        headers: await _headers(),
        body: jsonEncode({}),
      ),
      timeout: const Duration(seconds: 20),
    );

    _checkResponse(response);

    final data = jsonDecode(response.body) as Map<String, dynamic>;

    return data['id'] as String;
  }

  // ==========================================
  // GET CONVERSATION HISTORY
  // ==========================================

  Future<List<Map<String, dynamic>>> getConversations() async {
    final response = await _handleRequest(
      () async => http.get(
        Uri.parse('$baseUrl/conversations'),
        headers: await _headers(),
      ),
      timeout: const Duration(seconds: 20),
    );

    _checkResponse(response);

    final data = jsonDecode(response.body) as List<dynamic>;

    return data.map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }

  // ==========================================
  // GET MESSAGES FROM A CONVERSATION
  // ==========================================

  Future<List<Map<String, dynamic>>> getMessages(String conversationId) async {
    final response = await _handleRequest(
      () async => http.get(
        Uri.parse('$baseUrl/conversations/$conversationId'),
        headers: await _headers(),
      ),
      timeout: const Duration(seconds: 20),
    );

    _checkResponse(response);

    final data = jsonDecode(response.body) as Map<String, dynamic>;

    final messages = data['messages'] as List<dynamic>;

    return messages
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  // ==========================================
  // SEND MESSAGE TO VOCA MIND
  // ==========================================

  Future<String> sendMessage({
    required String conversationId,
    required String message,
  }) async {
    final result = await sendMessageDetailed(
      conversationId: conversationId,
      message: message,
    );
    return result['reply'] as String;
  }

  Future<Map<String, dynamic>> sendMessageDetailed({
    required String conversationId,
    required String message,
  }) async {
    if (message.trim().isEmpty) {
      throw Exception('Please enter a message.');
    }

    final response = await _handleRequest(
      () async => http.post(
        Uri.parse(
          '$baseUrl/conversations/'
          '$conversationId/messages',
        ),
        headers: await _headers(),
        body: jsonEncode({'role': 'user', 'content': message}),
      ),
      timeout: const Duration(seconds: 210),
    );

    _checkResponse(response);

    final data = jsonDecode(response.body) as Map<String, dynamic>;

    final assistantReply = data['assistant_reply'] as Map<String, dynamic>?;

    if (assistantReply == null) {
      throw Exception(
        'Voca Mind did not return a reply. '
        'Please check your chat history.',
      );
    }

    final content = assistantReply['content'];

    if (content is! String || content.trim().isEmpty) {
      throw Exception(
        'Voca Mind returned an empty response. '
        'Please check your chat history.',
      );
    }

    return {
      'reply': content,
      'support_offer': data['support_offer'],
      'is_human_takeover': data['is_human_takeover'] == true,
    };
  }
}
