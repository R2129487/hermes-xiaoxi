import 'package:flutter/material.dart';
import '../main.dart' show api;
import 'chat_detail.dart';
import '../services/app_config_service.dart';
import '../models/app_config.dart';
import '../models/agent.dart';

/// 办公组页面 — 微信群风格的工作组列表
class WorkgroupScreen extends StatefulWidget {
  const WorkgroupScreen({super.key});

  @override
  State<WorkgroupScreen> createState() => _WorkgroupScreenState();
}

class _WorkGroupViewModel {
  final String id;
  final String name;
  final String type;
  final List<Agent> agents;

  const _WorkGroupViewModel({required this.id, required this.name, required this.type, required this.agents});

  String get displayName => agents.isNotEmpty ? (agents.first.nickname.isNotEmpty ? agents.first.nickname : agents.first.displayName) : '?';
  String get lastMessage => '等待新消息';
  String get timeLabel => '';
  int get unread => 0;
}

class _WorkgroupScreenState extends State<WorkgroupScreen> {
  bool _loading = false;
  final TextEditingController _searchCtrl = TextEditingController();
  final Set<String> _collapsed = {};
  List<_WorkGroupViewModel> _groups = [];
  List<Agent> _agents = [];

  @override
  void initState() {
    super.initState();
    _searchCtrl.addListener(() => setState(() {}));
    _loadFromConfig();
    AppConfigService.instance.configNotifier.addListener(_loadFromConfig);
  }

  @override
  void dispose() {
    AppConfigService.instance.configNotifier.removeListener(_loadFromConfig);
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadFromConfig() async {
    setState(() => _loading = true);
    _agents = await api.getAgents();
    final groups = AppConfigService.instance.config?.groups ?? [];
    _groups = groups.map((g) {
      final members = AppConfigService.instance.resolveGroupMembersFuzzy(g, _agents);
      return _WorkGroupViewModel(id: g.id, name: g.name, type: g.type, agents: members);
    }).toList();
    if (mounted) setState(() => _loading = false);
  }

  // ─── 分组 ───
  List<_WorkGroupViewModel> get _permanent =>
      _groups.where((g) => g.type == 'permanent').toList();
  List<_WorkGroupViewModel> get _task =>
      _groups.where((g) => g.type == 'task').toList();
  List<_WorkGroupViewModel> get _emergency =>
      _groups.where((g) => g.type == 'emergency').toList();

  void _toggleSection(String key) {
    setState(() {
      if (_collapsed.contains(key)) {
        _collapsed.remove(key);
      } else {
        _collapsed.add(key);
      }
    });
  }

  Widget _buildSectionHeader(String title, {String? subtitle}) {
    final isCollapsed = _collapsed.contains(title);
    return GestureDetector(
      onTap: () => _toggleSection(title),
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
        color: Theme.of(context).brightness == Brightness.dark
            ? const Color(0xFF1A1A1A)
            : const Color(0xFFF7F7F7),
        child: Row(
          children: [
            Icon(
              isCollapsed ? Icons.chevron_right : Icons.expand_more,
              size: 16,
              color: Colors.grey[400],
            ),
            const SizedBox(width: 4),
            Text(
              title,
              style: TextStyle(
                color: Colors.grey[500],
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
            if (subtitle != null) ...[
              const SizedBox(width: 6),
              Text(
                subtitle,
                style: TextStyle(color: Colors.grey[400], fontSize: 11),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildGroupTile(_WorkGroupViewModel group) {
    final agents = group.agents;
    final unread = group.unread;

    // 组类型图标
    IconData typeIcon;
    Color typeColor;
    switch (group.type) {
      case 'task':
        typeIcon = Icons.assignment_outlined;
        typeColor = const Color(0xFFF59E0B);
        break;
      case 'emergency':
        typeIcon = Icons.warning_amber_outlined;
        typeColor = const Color(0xFFEF4444);
        break;
      default:
        typeIcon = Icons.group_outlined;
        typeColor = const Color(0xFF6366F1);
    }

    return InkWell(
      onTap: () {
        if (agents.isNotEmpty) {
          final first = agents.first;
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => ChatDetail(
                agentId: first.agentId,
                agentName: first.showName,
                agentColor: Color(first.avatarColor),
                agentAvatar: first.avatar,
                sessionId: 'session_agent_${first.agentId}',
              ),
            ),
          );
          return;
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('群聊功能开发中：${group.name}')),
        );
      },
      child: Container(
        color: Theme.of(context).cardColor,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            // 组头像（多成员头像堆叠）
            SizedBox(
              width: 48,
              height: 48,
              child: Stack(
                children: [
                  // 主头像
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: Color(agents.isNotEmpty ? agents.first.avatarColor : 0xFF6366F1),
                    child: Text(
                      group.displayName,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  // 副头像（右下角小圆）
                  if (agents.length > 1)
                    Positioned(
                      right: 0,
                      bottom: 0,
                      child: CircleAvatar(
                        radius: 10,
                        backgroundColor: Color(agents[1].avatarColor),
                        child: Text(
                          agents[1].displayName.isNotEmpty ? agents[1].displayName[0] : '?',
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 9,
                          ),
                        ),
                      ),
                    ),
                  // 类型标识（左上角小图标）
                  Positioned(
                    left: 0,
                    top: 0,
                    child: Container(
                      width: 18,
                      height: 18,
                      decoration: BoxDecoration(
                        color: Theme.of(context).cardColor,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(typeIcon, size: 14, color: typeColor),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            // 文字区域
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Row(
                          children: [
                            Flexible(
                              child: Text(
                                group.name,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w500,
                                  fontSize: 16,
                                  color: Color(0xFF191919),
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Text(
                              '${group.agents.length}人',
                              style: TextStyle(color: Colors.grey[400], fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                      Text(
                        group.timeLabel,
                        style: TextStyle(
                          color: unread > 0
                              ? const Color(0xFF07C160)
                              : Colors.grey[400],
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          group.lastMessage,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: Colors.grey[500],
                            fontSize: 13,
                          ),
                        ),
                      ),
                      if (unread > 0) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFEF4444),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            '$unread',
                            style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // 搜索栏
        Container(
          color: Theme.of(context).cardColor,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: Container(
            height: 36,
            decoration: BoxDecoration(
              color: const Color(0xFFF0F0F0),
              borderRadius: BorderRadius.circular(8),
            ),
            child: TextField(
              controller: _searchCtrl,
              style: const TextStyle(fontSize: 14),
              decoration: InputDecoration(
                hintText: '搜索办公组',
                hintStyle: TextStyle(color: Colors.grey[400], fontSize: 14),
                prefixIcon: Icon(Icons.search, color: Colors.grey[400], size: 20),
                border: InputBorder.none,
                contentPadding: const EdgeInsets.symmetric(vertical: 8),
                isCollapsed: true,
              ),
            ),
          ),
        ),

        // 列表
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: _loadFromConfig,
                  child: ListView(
                    padding: EdgeInsets.zero,
                    children: [
                      // ─── 常驻组 ───
                      if (_permanent.isNotEmpty) ...[
                        _buildSectionHeader('常驻组', subtitle: '${_permanent.length}'),
                        if (!_collapsed.contains('常驻组'))
                          ..._permanent.map((g) => _buildGroupTile(g)),
                      ],
                      // ─── 任务组 ───
                      if (_task.isNotEmpty) ...[
                        _buildSectionHeader('任务组', subtitle: '${_task.length}'),
                        if (!_collapsed.contains('任务组'))
                          ..._task.map((g) => _buildGroupTile(g)),
                      ],
                      // ─── 紧急组 ───
                      if (_emergency.isNotEmpty) ...[
                        _buildSectionHeader('紧急组', subtitle: '${_emergency.length}'),
                        if (!_collapsed.contains('紧急组'))
                          ..._emergency.map((g) => _buildGroupTile(g)),
                      ],
                      // ─── 空状态 ───
                      if (_groups.isEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 80),
                          child: Center(
                            child: Column(
                              children: [
                                Icon(Icons.group_outlined, size: 48, color: Colors.grey[300]),
                                const SizedBox(height: 12),
                                Text(
                                  '暂无办公组',
                                  style: TextStyle(color: Colors.grey[500], fontSize: 14),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '在服务端管理页面创建工作流组后自动同步',
                                  style: TextStyle(color: Colors.grey[400], fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                        ),
                      // ─── 新建按钮 ───
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                        child: SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('创建办公组请前往服务端管理页面')),
                              );
                            },
                            icon: const Icon(Icons.add, size: 18),
                            label: const Text('新建办公组'),
                            style: OutlinedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              side: BorderSide(color: Colors.grey[300]!),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                    ],
                  ),
                ),
        ),
      ],
    );
  }
}
