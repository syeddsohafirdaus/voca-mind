class SupportOffer {
  final String message;

  const SupportOffer({required this.message});

  static SupportOffer? fromJson(dynamic data) {
    if (data is! Map) return null;

    if (data['offered'] != true ||
        data['action'] != 'request_professional_support' ||
        data['requires_consent'] != true ||
        data['automatic_notification'] != false ||
        data['emergency_service'] != false) {
      return null;
    }

    final message = data['message'];

    if (message is! String || message.trim().isEmpty) {
      return null;
    }

    return SupportOffer(message: message);
  }
}
