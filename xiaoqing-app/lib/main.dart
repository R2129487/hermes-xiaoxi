import 'package:flutter/material.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'services/dispatcher_api.dart';

/// 全局主题切换
final ValueNotifier<ThemeMode> themeNotifier = ValueNotifier(ThemeMode.light);

/// 全局 API 实例
final DispatcherApi api = DispatcherApi();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await api.init();
  runApp(const XiaoQingApp());
}

class XiaoQingApp extends StatefulWidget {
  const XiaoQingApp({super.key});

  @override
  State<XiaoQingApp> createState() => _XiaoQingAppState();
}

class _XiaoQingAppState extends State<XiaoQingApp> {
  bool _checking = true;
  bool _authenticated = false;

  @override
  void initState() {
    super.initState();
    themeNotifier.addListener(_onThemeChange);
    _checkAuth();
  }

  @override
  void dispose() {
    themeNotifier.removeListener(_onThemeChange);
    super.dispose();
  }

  void _onThemeChange() => setState(() {});

  Future<void> _checkAuth() async {
    if (api.isLoggedIn) {
      final valid = await api.getMe();
      if (mounted) {
        setState(() {
          _authenticated = valid;
          _checking = false;
        });
      }
    } else {
      if (mounted) {
        setState(() {
          _authenticated = false;
          _checking = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '小希',
      debugShowCheckedModeBanner: false,
      themeMode: themeNotifier.value,
      theme: ThemeData(
        brightness: Brightness.light,
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A73E8),
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFEDEDED),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFEDEDED),
          foregroundColor: Color(0xFF191919),
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: Color(0xFF191919),
            fontSize: 17,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      darkTheme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A73E8),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF111111),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF1A1A1A),
          foregroundColor: Color(0xFFE0E0E0),
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: Color(0xFFE0E0E0),
            fontSize: 17,
            fontWeight: FontWeight.w600,
          ),
        ),
        cardColor: const Color(0xFF1E1E1E),
        dividerColor: const Color(0xFF2A2A2A),
      ),
      home: _buildHome(),
    );
  }

  Widget _buildHome() {
    if (_checking) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    if (_authenticated) {
      return const HomeScreen();
    }
    return LoginScreen(api: api);
  }
}
