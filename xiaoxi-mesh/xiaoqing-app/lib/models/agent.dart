/// 智能体模型
class Agent {
  final String agentId;
  final String displayName;
  final String nickname;       // 用户自定义备注名
  final String type;           // dispatcher/agent/user
  final String avatar;
  final int avatarColor;       // 头像背景色 ARGB int
  final bool online;
  final String status;         // online/offline/thinking/working/idle
  final bool pinned;           // 是否置顶
  final String capabilities;
  final String connectionType; // local/ssh/mesh/http
  final String connectionInfo; // IP:port 或 user@host
  final String description;    // 智能体描述

  Agent({
    required this.agentId,
    this.displayName = '',
    this.nickname = '',
    this.type = 'agent',
    this.avatar = '?',
    this.avatarColor = 0xFF888888,
    this.online = false,
    this.status = 'offline',
    this.pinned = false,
    this.capabilities = '',
    this.connectionType = '',
    this.connectionInfo = '',
    this.description = '',
  });

  /// 显示名：备注名 > 默认名
  String get showName => nickname.isNotEmpty ? nickname : displayName;

  /// 排序权重：调度员→置顶→在线→离线
  int get sortWeight {
    if (type == 'dispatcher') return 0;    // 调度员永远最顶
    if (pinned) return 1;                   // 置顶第二
    if (online) return 2;                   // 在线第三
    return 3;                               // 离线最后
  }

  /// 连接方式中文标签
  String get connectionTypeLabel {
    switch (connectionType) {
      case 'local': return '本机';
      case 'ssh': return 'SSH';
      case 'mesh': return 'MESH';
      case 'http': return 'HTTP';
      default: return connectionType;
    }
  }

  factory Agent.fromJson(Map<String, dynamic> json) {
    // 构建连接信息
    String connInfo = '';
    final connType = json['connection_type'] ?? '';
    if (connType == 'ssh') {
      final user = json['ssh_user'] ?? '';
      final host = json['host'] ?? '';
      final port = json['port'] ?? '';
      connInfo = port != null && port != '' ? '$user@$host:$port' : '$user@$host';
    } else if (connType == 'mesh' || connType == 'http') {
      final host = json['host'] ?? '';
      final port = json['port'] ?? '';
      connInfo = port != null && port != '' ? '$host:$port' : host;
    }

    return Agent(
      agentId: json['agent_id'] ?? json['id'] ?? '',
      displayName: json['name'] ?? '',
      nickname: json['nickname'] ?? '',
      type: json['type'] ?? 'agent',
      avatar: json['avatar'] ?? (json['name']?.toString().isNotEmpty == true ? json['name'][0] : '?'),
      avatarColor: json['avatar_color'] ?? 0xFF888888,
      online: json['status'] != 'offline',
      status: json['status'] ?? 'offline',
      pinned: json['pinned'] ?? false,
      capabilities: json['capabilities'] ?? '',
      connectionType: connType,
      connectionInfo: connInfo,
      description: json['description'] ?? '',
    );
  }
}
