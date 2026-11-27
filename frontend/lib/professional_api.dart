import 'dart:convert';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;

import 'api_service.dart';

class ProfessionalApi {
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    Map<String, String>? query,
  }) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      throw Exception('Please sign in again.');
    }

    final token = await user.getIdToken();
    if (token == null || token.isEmpty) {
      throw Exception('Authentication unavailable.');
    }

    final uri = Uri.parse('${ApiService.baseUrl}$path')
        .replace(queryParameters: query);

    final headers = {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };

    final http.Response response;

    if (method == 'GET') {
      response = await http
          .get(uri, headers: headers)
          .timeout(const Duration(seconds: 25));
    } else if (method == 'POST') {
      response = await http
          .post(
            uri,
            headers: headers,
            body: body == null ? null : jsonEncode(body),
          )
          .timeout(const Duration(seconds: 25));
    } else {
      throw Exception('Unsupported request method.');
    }

    if (FirebaseAuth.instance.currentUser?.uid != user.uid) {
      throw Exception('Account changed. Please reopen this screen.');
    }

    if (response.statusCode == 409) {
      throw Exception(
        'The request state has changed. Refresh before continuing.',
      );
    }

    if (response.statusCode == 401 || response.statusCode == 403) {
      throw Exception('Access is unavailable for this account.');
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(
        'Request unsuccessful (${response.statusCode}). Refresh before retrying.',
      );
    }

    return response.body.isEmpty ? null : jsonDecode(response.body);
  }

  Future<List<Map<String, dynamic>>> list(
    String path, {
    Map<String, String>? query,
  }) async {
    final result = await request(path, query: query);
    return (result as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  Future<dynamic> dashboard() => request('/doctors/dashboard');

  Future<List<Map<String, dynamic>>> assignments(String role) =>
      list('/assignments/$role');

  Future<List<Map<String, dynamic>>> supportRequests() =>
      list('/support/client');

  Future<dynamic> requestSupport({String source = 'client'}) => request(
    '/support/request',
    method: 'POST',
    body: {'source': source, 'consent': true},
  );

  Future<dynamic> cancelSupport(String id) =>
      request('/support/$id/cancel', method: 'POST');

  Future<dynamic> assignmentAction(String id, String action) =>
      request('/assignments/$id/$action', method: 'POST');

  Future<List<Map<String, dynamic>>> messages(String id) =>
      list('/professional/$id/messages', query: {'limit': '50'});

  Future<dynamic> sendMessage(String id, String content) => request(
    '/professional/$id/messages',
    method: 'POST',
    body: {'content': content},
  );

  Future<dynamic> readMessage(String id, String messageId) =>
      request('/professional/$id/messages/$messageId/read', method: 'POST');

  Future<List<Map<String, dynamic>>> takeovers(String role) =>
      list('/takeovers/$role', query: {'limit': '100'});

  Future<dynamic> requestTakeover(String id) => request(
    '/takeovers/$id/request',
    method: 'POST',
    body: {'consent': true},
  );

  Future<dynamic> takeoverAction(
    String assignmentId,
    String takeoverId,
    String action,
  ) => request(
    '/takeovers/$assignmentId/$action',
    method: 'POST',
    query: {'takeover_id': takeoverId},
  );

  Future<List<Map<String, dynamic>>> notifications() => list('/notifications');

  Future<dynamic> readNotification(String id) =>
      request('/notifications/$id/read', method: 'POST');
}
