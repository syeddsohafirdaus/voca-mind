import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voca_mind/professional_consent.dart';

Future<void> openConsent(
  WidgetTester tester,
  ValueChanged<bool> onResult,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => ElevatedButton(
            onPressed: () async {
              final result = await confirmProfessionalAction(
                context,
                'Professional support',
                'Your AI conversations will not be shared.',
              );
              onResult(result);
            },
            child: const Text('Request support'),
          ),
        ),
      ),
    ),
  );

  await tester.tap(find.text('Request support'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('Consent dialog displays privacy information', (tester) async {
    await openConsent(tester, (_) {});

    expect(find.text('Professional support'), findsOneWidget);
    expect(
      find.text('Your AI conversations will not be shared.'),
      findsOneWidget,
    );
    expect(find.text('Confirm'), findsOneWidget);
    expect(find.text('Cancel'), findsOneWidget);
  });

  testWidgets('Cancelling does not grant consent', (tester) async {
    bool? result;

    await openConsent(tester, (value) => result = value);

    expect(result, isNull);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(result, isFalse);
  });

  testWidgets('Confirmation grants explicit consent', (tester) async {
    bool? result;

    await openConsent(tester, (value) => result = value);

    expect(result, isNull);

    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();

    expect(result, isTrue);
  });

  testWidgets('Outside tap does not grant consent', (tester) async {
    bool? result;

    await openConsent(tester, (value) => result = value);

    await tester.tapAt(const Offset(5, 5));
    await tester.pumpAndSettle();

    expect(result, isNull);
    expect(find.text('Confirm'), findsOneWidget);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(result, isFalse);
  });
}
