
import 'package:shared_preferences/shared_preferences.dart';

class VoicePreferences {
  static const String _enabledKey = 'voice_enabled';
  static const String _speedKey = 'voice_speed';
  static const String _languageKey = 'voice_language';

  static Future<bool> getVoiceEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_enabledKey) ?? true;
  }

  static Future<void> setVoiceEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_enabledKey, enabled);
  }

  static Future<double> getSpeechSpeed() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getDouble(_speedKey) ?? 0.48;
  }

  static Future<void> setSpeechSpeed(double speed) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_speedKey, speed);
  }

  static Future<String> getLanguage() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_languageKey) ?? 'en-IN';
  }

  static Future<void> setLanguage(String language) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_languageKey, language);
  }
}
