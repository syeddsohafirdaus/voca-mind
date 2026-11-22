
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voca_mind/main.dart';

void main() {
  testWidgets('Voca Mind welcome screen displays correctly', (tester) async {
    await tester.pumpWidget(const VocaMindApp());

    expect(find.text('Voca Mind'), findsOneWidget);
    expect(
      find.text('Your AI-Powered Conversational Assistant'),
      findsOneWidget,
    );
    expect(find.byIcon(Icons.psychology), findsOneWidget);
  });
}
