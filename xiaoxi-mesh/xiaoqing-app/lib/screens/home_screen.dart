import 'package:flutter/material.dart';
import 'chat_screen.dart';
import 'contacts_screen.dart';
import 'workgroup_screen.dart';
import 'settings_screen.dart';
import '../services/app_config_service.dart';
import '../models/app_config.dart';

/// 主页 — 微信风格底部导航
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;
  late List<Widget> _pages;
  late List<String> _titles;

  @override
  void initState() {
    super.initState();
    _refreshFromConfig();
    AppConfigService.instance.configNotifier.addListener(_refreshFromConfig);
  }

  @override
  void dispose() {
    AppConfigService.instance.configNotifier.removeListener(_refreshFromConfig);
    super.dispose();
  }

  void _refreshFromConfig() {
    final config = AppConfigService.instance.config;
    final nav = config?.bottomNav ?? [];
    final pages = <Widget>[
      const ConversationList(),
      if (nav.any((n) => n.key == 'workgroup')) const WorkgroupScreen(),
      const ContactsScreen(),
      const SettingsScreen(),
    ];
    final titles = nav.map((n) => n.label).toList();
    _pages = pages;
    _titles = titles;
    if (_currentIndex >= _pages.length) _currentIndex = 0;
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_titles.isNotEmpty ? _titles[_currentIndex.clamp(0, _titles.length - 1)] : '小希'),
      ),
      body: _pages.isNotEmpty ? _pages[_currentIndex.clamp(0, _pages.length - 1)] : const SizedBox.shrink(),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        type: BottomNavigationBarType.fixed,
        selectedItemColor: const Color(0xFF07C160),
        unselectedItemColor: Colors.grey,
        selectedFontSize: 10,
        unselectedFontSize: 10,
        iconSize: 24,
        items: [
          const BottomNavigationBarItem(icon: Icon(Icons.chat_bubble_outline), activeIcon: Icon(Icons.chat_bubble), label: '聊天'),
          if (AppConfigService.instance.config?.bottomNav.any((n) => n.key == 'workgroup') ?? true)
            const BottomNavigationBarItem(icon: Icon(Icons.workspaces_outlined), activeIcon: Icon(Icons.workspaces), label: '办公组'),
          const BottomNavigationBarItem(icon: Icon(Icons.contacts_outlined), activeIcon: Icon(Icons.contacts), label: '联系人'),
          const BottomNavigationBarItem(icon: Icon(Icons.settings_outlined), activeIcon: Icon(Icons.settings), label: '设置'),
        ],
      ),
    );
  }
}
