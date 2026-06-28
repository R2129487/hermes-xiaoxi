import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../models/app_config.dart';
import '../models/agent.dart';

/// APP配置服务：启动拉取 + 定时刷新 + 联网覆盖
class AppConfigService {
  static final AppConfigService instance = AppConfigService._();
  AppConfigService._();

  AppConfig? _config;
  Timer? _timer;
  final ValueNotifier<AppConfig?> configNotifier = AppConfigNotifier(null);

  AppConfig? get config => _config;

  /// 启动时加载：先加载本地默认，再拉服务端覆盖
  Future<void> init(String baseUrl) async {
    _config = AppConfig.fromJson(_defaultJson());
    configNotifier.value = _config;

    await _fetchFromServer(baseUrl);
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(minutes: 5), (_) => _fetchFromServer(baseUrl));
  }

  /// 根据当前配置把智能体过滤成工作组成员
  List<Agent> resolveGroupMembers(AppWorkGroup group, List<Agent> allAgents) {
    final ids = group.memberIds.map((e) => e.toLowerCase()).toSet();
    return allAgents.where((a) => ids.contains(a.agentId.toLowerCase())).toList();
  }

  /// 根据当前配置把智能体过滤成工作组成员（支持 agentId / displayName / nickname）
  List<Agent> resolveGroupMembersFuzzy(AppWorkGroup group, List<Agent> allAgents) {
    final ids = group.memberIds.map((e) => e.toLowerCase()).toSet();
    return allAgents.where((a) {
      if (ids.contains(a.agentId.toLowerCase())) return true;
      if (ids.contains(a.displayName.toLowerCase())) return true;
      if (a.nickname.isNotEmpty && ids.contains(a.nickname.toLowerCase())) return true;
      return false;
    }).toList();
  }

  Future<void> _fetchFromServer(String baseUrl) async {
    try {
      final r = await http.get(Uri.parse('$baseUrl/api/app-config')).timeout(const Duration(seconds: 6));
      if (r.statusCode != 200) return;
      final data = json.decode(r.body);
      if (data['code'] != 0) return;
      _config = AppConfig.fromJson(data['data']);
      configNotifier.value = _config;
    } catch (_) {
      // 网络失败保持本地默认，不影响体验
    }
  }

  Map<String, dynamic> _defaultJson() => {
    'title': '小希',
    'logoText': '青',
    'version': {'label': '0.0.0'},
    'features': {
      'darkMode': true,
      'voiceInput': true,
      'notifications': true,
      'groupChat': true,
    },
    'bottomNav': [
      {'key': 'chat', 'label': '聊天', 'icon': 'chat_bubble'},
      {'key': 'workgroup', 'label': '办公组', 'icon': 'workspaces'},
      {'key': 'contacts', 'label': '联系人', 'icon': 'contacts'},
      {'key': 'settings', 'label': '设置', 'icon': 'settings'},
    ],
    'groups': [],
    'aiAgents': [],
    'users': [],
    'ui': {'themePrimary': '#1A73E8', 'showStatusIndicator': true},
  };
}

class AppConfigNotifier extends ValueNotifier<AppConfig?> {
  AppConfigNotifier(super.value);
}
