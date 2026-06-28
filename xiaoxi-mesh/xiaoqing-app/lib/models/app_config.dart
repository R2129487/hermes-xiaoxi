/// 服务端下发的APP配置模型
class AppConfig {
  final String versionLabel;
  final String title;
  final String logoText;
  final Map<String, bool> features;
  final List<BottomNavItem> bottomNav;
  final List<AppWorkGroup> groups;
  final List<AppAgentConfig> agents;
  final List<AppUserConfig> users;
  final int themePrimary;
  final bool showStatusIndicator;

  AppConfig({
    required this.versionLabel,
    required this.title,
    required this.logoText,
    required this.features,
    required this.bottomNav,
    required this.groups,
    required this.agents,
    required this.users,
    required this.themePrimary,
    required this.showStatusIndicator,
  });

  factory AppConfig.fromJson(Map<String, dynamic> json) {
    final version = json['version'] as Map<String, dynamic>? ?? {};
    final ui = json['ui'] as Map<String, dynamic>? ?? {};

    final groups = (json['groups'] as List<dynamic>? ?? []).map((g) {
      final map = g as Map<String, dynamic>;
      return AppWorkGroup(
        id: map['id'] ?? '',
        name: map['name'] ?? '',
        type: map['type'] ?? 'task',
        memberIds: List<String>.from(map['members'] ?? []),
      );
    }).toList();

    final agents = (json['aiAgents'] as List<dynamic>? ?? []).map((a) {
      final map = a as Map<String, dynamic>;
      return AppAgentConfig(
        id: map['id'] ?? '',
        name: map['name'] ?? '',
        role: map['role'] ?? '',
        color: map['color'] ?? '',
        capabilities: List<String>.from(map['capabilities'] ?? []),
      );
    }).toList();

    final users = (json['users'] as List<dynamic>? ?? []).map((u) {
      final map = u as Map<String, dynamic>;
      return AppUserConfig(
        id: map['id'] ?? '',
        name: map['name'] ?? '',
        role: map['role'] ?? '',
        color: map['color'] ?? '',
      );
    }).toList();

    final nav = (json['bottomNav'] as List<dynamic>? ?? []).map((n) {
      final map = n as Map<String, dynamic>;
      return BottomNavItem(
        key: map['key'] ?? '',
        label: map['label'] ?? '',
        icon: map['icon'] ?? 'circle',
      );
    }).toList();

    final themeColorStr = ui['themePrimary'] ?? '#1A73E8';
    final themeColor = _parseHexColor(themeColorStr);

    return AppConfig(
      versionLabel: version['label'] ?? '0.0.0',
      title: json['title'] ?? '小希',
      logoText: json['logoText'] ?? '青',
      features: Map<String, bool>.from(json['features'] ?? {}),
      bottomNav: nav,
      groups: groups,
      agents: agents,
      users: users,
      themePrimary: themeColor,
      showStatusIndicator: ui['showStatusIndicator'] ?? true,
    );
  }

  static int _parseHexColor(String hex) {
    final cleaned = hex.replaceAll('#', '');
    try {
      return int.parse('FF$cleaned', radix: 16);
    } catch (_) {
      return 0xFF1A73E8;
    }
  }
}

class BottomNavItem {
  final String key;
  final String label;
  final String icon;

  const BottomNavItem({required this.key, required this.label, required this.icon});
}

class AppWorkGroup {
  final String id;
  final String name;
  final String type;
  final List<String> memberIds;

  const AppWorkGroup({required this.id, required this.name, required this.type, required this.memberIds});
}

class AppAgentConfig {
  final String id;
  final String name;
  final String role;
  final String color;
  final List<String> capabilities;

  const AppAgentConfig({required this.id, required this.name, required this.role, required this.color, required this.capabilities});
}

class AppUserConfig {
  final String id;
  final String name;
  final String role;
  final String color;

  const AppUserConfig({required this.id, required this.name, required this.role, required this.color});
}
