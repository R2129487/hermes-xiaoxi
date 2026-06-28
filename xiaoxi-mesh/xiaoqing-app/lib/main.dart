import 'dart:async';
import 'package:flutter/material.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart';
import 'package:flutter/services.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'screens/chat_detail.dart';
import 'models/agent.dart';
import 'services/dispatcher_api.dart';
import 'services/notification_service.dart';
import 'services/app_config_service.dart';

/// APP全局标题（跟随服务端配置）
final ValueNotifier<String> appTitleNotifier = ValueNotifier('小希');

/// 全局主题切换
final ValueNotifier<ThemeMode> themeNotifier = ValueNotifier(ThemeMode.light);

/// 全局 API 实例
final DispatcherApi api = DispatcherApi();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 初始化 sherpa-onnx 语音引擎 native 库
  try {
    initBindings();
    print('[main] ✅ sherpa-onnx 绑定初始化成功');
  } catch (e) {
    print('[main] ❌ sherpa-onnx 初始化失败: $e');
  }

  await api.init();
  // 初始化通知
  await NotificationService().init();
  // 初始化APP配置（拉服务端最新配置）
  await AppConfigService.instance.init(api.baseUrl);
  if (AppConfigService.instance.config != null) {
    appTitleNotifier.value = AppConfigService.instance.config!.title;
  }
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
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    themeNotifier.addListener(_onThemeChange);
    _setupNotificationTap();
    _checkAuth();
  }

  @override
  void dispose() {
    themeNotifier.removeListener(_onThemeChange);
    super.dispose();
  }

  void _onThemeChange() => setState(() {});

  void _setupNotificationTap() {
    NotificationService().onNotificationTap = (payload) {
      print('[main] 🔔 通知点击跳转: $payload');
      // payload 格式: "agent_id|agent_name|agent_color|session_id"
      final parts = payload.split('|');
      if (parts.length >= 4 && _navigatorKey.currentState != null) {
        final agentId = parts[0];
        final agentName = parts[1];
        final agentColor = int.tryParse(parts[2]) ?? 0xFF6366F1;
        final sessionId = parts[3];
        _navigatorKey.currentState!.push(
          MaterialPageRoute(
            builder: (_) => ChatDetail(
              agentId: agentId,
              agentName: agentName,
              agentColor: Color(agentColor),
              agentAvatar: agentName.isNotEmpty ? agentName[0] : '?',
              sessionId: sessionId,
            ),
          ),
        );
      }
    };
  }

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
      title: appTitleNotifier.value,
      debugShowCheckedModeBanner: false,
      navigatorKey: _navigatorKey,
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
