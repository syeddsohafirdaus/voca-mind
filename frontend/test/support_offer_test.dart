import 'package:flutter_test/flutter_test.dart';
import 'package:voca_mind/support_offer.dart';

void main() {
  final valid = <String, dynamic>{
    'offered': true,
    'message': 'Professional support is available to request.',
    'action': 'request_professional_support',
    'requires_consent': true,
    'automatic_notification': false,
    'emergency_service': false,
  };

  test('Valid offer is accepted', () {
    expect(SupportOffer.fromJson(valid), isNotNull);
  });

  test('Missing offer is ignored', () {
    expect(SupportOffer.fromJson(null), isNull);
  });

  test('Inactive offer is ignored', () {
    expect(SupportOffer.fromJson({...valid, 'offered': false}), isNull);
  });

  test('Automatic notification is rejected', () {
    expect(
      SupportOffer.fromJson({...valid, 'automatic_notification': true}),
      isNull,
    );
  });

  test('Consent bypass is rejected', () {
    expect(
      SupportOffer.fromJson({...valid, 'requires_consent': false}),
      isNull,
    );
  });

  test('Emergency service claim is rejected', () {
    expect(
      SupportOffer.fromJson({...valid, 'emergency_service': true}),
      isNull,
    );
  });

  test('Unknown action is rejected', () {
    expect(SupportOffer.fromJson({...valid, 'action': 'unknown'}), isNull);
  });

  test('Empty message is rejected', () {
    expect(SupportOffer.fromJson({...valid, 'message': ''}), isNull);
  });
}
