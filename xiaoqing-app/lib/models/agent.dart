/// 智能体模型
class Agent {
  final String agentId;
  final String displayName;
  final String nickname;       // 用户自定义备注名
  final String type;           // dispatcher/agent/user
  final String avatar;
  final int avatarColor;       // 头像背景色 ARGB int
  final bool online;
  final bool pinned;           // 是否置顶
  final String capabilities;

  Agent({
    required this.agentId,
    this.displayName = '',
    this.nickname = '',
    this.type = 'agent',
    this.avatar = '?',
    this.avatarColor = 0xFF888888,
    this.online = false,
    this.pinned = false,
    this.capabilities = '',
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

  factory Agent.fromJson(Map<String, dynamic> json) {
    return Agent(
      agentId: json['id'] ?? '',
      displayName: json['name'] ?? '',
      nickname: json['nickname'] ?? '',
      type: json['type'] ?? 'agent',
      avatar: json['avatar'] ?? (json['name']?.toString().isNotEmpty == true ? json['name'][0] : '?'),
      avatarColor: json['avatar_color'] ?? 0xFF888888,
      online: json['status'] == 'online',
      pinned: json['pinned'] ?? false,
      capabilities: json['capabilities'] ?? '',
    );
  }
}
