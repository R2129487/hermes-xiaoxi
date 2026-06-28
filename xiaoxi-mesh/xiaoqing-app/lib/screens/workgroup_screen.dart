import 'package:flutter/material.dart';
import '../main.dart' show api;
import 'chat_detail.dart';

/// 办公组页面 — 微信群风格的工作组列表
class WorkgroupScreen extends StatefulWidget {
  const WorkgroupScreen({super.key});

  @override
  State<WorkgroupScreen> createState() => _WorkgroupScreenState();
}

class _WorkgroupScreenState extends State<WorkgroupScreen> {
  bool _loading = false;
  final TextEditingController _searchCtrl = TextEditingController();
  final Set<String> _collapsed = {};

  // ─── 模拟数据（后续接 API） ───
  final List<Map<String, dynamic>> _groups = [
    {
      'id': 'g_dev',
      'name': '开发组',
      'type': 'permanent',  // permanent=常驻, task=任务, emergency=紧急
      'members': ['青', '蓝', '白'],
      'memberColors': [0xFF6366F1, 0xFF8B5CF6, 0xFF34D399],
      'lastMsg': '小蓝：服务器部署完成',
      'time': '14:32',
      'unread': 2,
    },
    {
      'id': 'g_ops',
      'name': '运维值班',
      'type': 'permanent',
      'members': ['蓝', '黑'],
      'memberColors': [0xFF8B5CF6, 0xFF64748B],
      'lastMsg': '小黑：巡检报告已提交',
      'time': '13:15',
      'unread': 0,
    },
    {
      'id': 'g_task_v013',
      'name': 'v0.1.3 发版任务',
      'type': 'task',
      'members': ['青', '蓝'],
      'memberColors': [0xFF6366F1, 0xFF8B5CF6],
      'lastMsg': '小青：APK 已构建完成',
      'time': '16:53',
      'unread': 1,
    },
  ];

  @override
  void initState() {
    super.initState();
    _searchCtrl.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  // ─── 分组 ───
  List<Map<String, dynamic>> get _permanent =>
      _groups.where((g) => g['type'] == 'permanent').toList();
  List<Map<String, dynamic>> get _task =>
      _groups.where((g) => g['type'] == 'task').toList();
  List<Map<String, dynamic>> get _emergency =>
      _groups.where((g) => g['type'] == 'emergency').toList();

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

  Widget _buildGroupTile(Map<String, dynamic> group) {
    final members = group['members'] as List<String>;
    final colors = group['memberColors'] as List<int>;
    final unread = group['unread'] as int;

    // 组类型图标
    IconData typeIcon;
    Color typeColor;
    switch (group['type']) {
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
        // TODO: 进入群聊
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('群聊功能开发中：${group['name']}')),
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
                    backgroundColor: Color(colors.isNotEmpty ? colors[0] : 0xFF6366F1),
                    child: Text(
                      members.isNotEmpty ? members[0] : '?',
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  // 副头像（右下角小圆）
                  if (members.length > 1)
                    Positioned(
                      right: 0,
                      bottom: 0,
                      child: CircleAvatar(
                        radius: 10,
                        backgroundColor: Color(colors.length > 1 ? colors[1] : 0xFF8B5CF6),
                        child: Text(
                          members[1],
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
                                group['name'],
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
                              '${members.length}人',
                              style: TextStyle(color: Colors.grey[400], fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                      Text(
                        group['time'] ?? '',
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
                          group['lastMsg'] ?? '',
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
                  onRefresh: () async {},
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
                                  '创建一个工作组开始协作',
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
                              // TODO: 新建办公组
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('创建办公组功能开发中')),
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
