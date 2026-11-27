import 'api_service.dart';

class GuardianApi {
  final ApiService _api = ApiService();

  Future<List<Map<String, dynamic>>> getAuthorizations() async {
    final data = await _api.requestJson('GET', '/guardians/authorizations');

    return (data as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  Future<Map<String, dynamic>> grant({
    required String guardianId,
    required bool consent,
  }) async {
    if (!consent) {
      throw ArgumentError('Explicit consent is required.');
    }

    final data = await _api.requestJson(
      'POST',
      '/guardians/authorizations',
      body: {'guardian_id': guardianId.trim(), 'consent': consent},
    );

    return Map<String, dynamic>.from(data as Map);
  }

  Future<void> revoke({
    required String authorizationId,
    required String consentVersion,
  }) async {
    await _api.requestJson(
      'POST',
      '/guardians/authorizations/$authorizationId/revoke',
      query: {'consent_version': consentVersion},
    );
  }

  Future<void> shareWellbeing({
    required String authorizationId,
    required String consentVersion,
    required String wellbeing,
    required bool consent,
  }) async {
    if (!consent) {
      throw ArgumentError('Explicit consent is required.');
    }

    await _api.requestJson(
      'POST',
      '/guardians/authorizations/$authorizationId/wellbeing',
      query: {'consent_version': consentVersion},
      body: {'wellbeing': wellbeing, 'consent': consent},
    );
  }

  Future<void> withdrawWellbeing({
    required String authorizationId,
    required String consentVersion,
  }) async {
    await _api.requestJson(
      'DELETE',
      '/guardians/authorizations/$authorizationId/wellbeing',
      query: {'consent_version': consentVersion},
    );
  }

  Future<List<Map<String, dynamic>>> getDashboard({
    int limit = 50,
    int offset = 0,
  }) async {
    final data = await _api.requestJson(
      'GET',
      '/guardians/dashboard',
      query: {'limit': '$limit', 'offset': '$offset'},
    );

    return (data as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }
}
