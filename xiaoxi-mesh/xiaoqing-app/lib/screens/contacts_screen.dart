import 'package:flutter/material.dart';
import '../main.dart' show api;
import '../models/agent.dart';
import 'chat_detail.dart';
import 'agent_settings_screen.dart';

/// 联系人页面 — 分组显示：调度员置顶 + 成员可搜索
class ContactsScreen extends StatefulWidget {
  const ContactsScreen({super.key});

  @override
  State<ContactsScreen> createState() => _ContactsScreenState();
}

class _ContactsScreenState extends State<ContactsScreen> {
  List<Agent> _agents = [];
  List<Agent> _filtered = [];
  bool _loading = true;
  final TextEditingController _searchCtrl = TextEditingController();
  final Set<String> _collapsed = {};  // 折叠的分栏 key

  @override
  void initState() {
    super.initState();
    _loadAgents();
    _searchCtrl.addListener(() { _filter(null); });
  }

  void _toggleSection(String key) {
    setState(() {
      if (_collapsed.contains(key)) {
        _collapsed.remove(key);
      } else {
        _collapsed.add(key);
      }
    });
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadAgents() async {
    setState(() => _loading = true);
    final agents = await api.getAgents();
    // 排序：调度员→置顶→在线→离线
    agents.sort((a, b) {
      final w = a.sortWeight.compareTo(b.sortWeight);
      if (w != 0) return w;
      return a.showName.compareTo(b.showName);
    });
    if (mounted) setState(() { _agents = agents; _filter(''); _loading = false; });
  }

  void _filter(_) {
    final q = _searchCtrl.text.trim().toLowerCase();
    setState(() {
      _filtered = q.isEmpty ? _agents : _agents.where((a) =>
        a.showName.toLowerCase().contains(q) ||
        a.agentId.toLowerCase().contains(q)
      ).toList();
    });
  }

  // 从列表中分离调度员、智能体、用户
  bool _isSelf(Agent a) {
    final uid = api.currentUser?.id ?? '';
    return uid.isNotEmpty && a.agentId == 'user_$uid';
  }

  List<Agent> get _dispatchers => _filtered.where((a) => a.type == 'dispatcher').toList();
  List<Agent> get _agentList => _filtered.where((a) => a.type == 'agent').toList();
  List<Agent> get _userList => _filtered.where((a) => a.type == 'user' && !_isSelf(a)).toList();

  String _agentAvatar(String id) {
    switch (id) {
      case 'dispatcher': return '调';
      case 'xiaoqing': return '青';
      case 'xiaolan': return '蓝';
      case 'xiaobai': return '白';
      case 'xiaohei': return '黑';
      default: return '?';
    }
  }

  /// 状态中文映射
  String _statusLabel(String status) {
    switch (status) {
      case 'online': return '🟢 在线';
      case 'thinking': return '💭 思考中';
      case 'working': return '⚙️ 工作中';
      case 'idle': return '💤 空闲';
      case 'offline': return '🔴 离线';
      default: return status;
    }
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
                hintText: '搜索联系人',
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
                  onRefresh: _loadAgents,
                  child: ListView(
                    padding: EdgeInsets.zero,
                    children: [
                      // ─── 调度员（置顶） ───
                      if (_dispatchers.isNotEmpty) ...[
                        _buildSectionHeader('调度员', 'top', count: _dispatchers.length),
                        if (!_collapsed.contains('调度员'))
                          ..._dispatchers.map((a) => _buildAgentTile(a)),
                      ],
                      // ─── 智能体 ───
                      if (_agentList.isNotEmpty) ...[
                        _buildSectionHeader('智能体', 'bottom', count: _agentList.length),
                        if (!_collapsed.contains('智能体'))
                          ..._agentList.map((a) => _buildAgentTile(a)),
                      ],
                      // ─── 用户 ───
                      if (_userList.isNotEmpty) ...[
                        _buildSectionHeader('用户', 'bottom', count: _userList.length),
                        if (!_collapsed.contains('用户'))
                          ..._userList.map((a) => _buildAgentTile(a)),
                      ],
                      // ─── 搜索无结果 ───
                      if (_filtered.isEmpty && !_loading)
                        Padding(
                          padding: const EdgeInsets.only(top: 80),
                          child: Center(
                            child: Text(
                              _searchCtrl.text.isEmpty ? '暂无智能体' : '没有找到「${_searchCtrl.text}」',
                              style: TextStyle(color: Colors.grey[500], fontSize: 14),
                            ),
                          ),
                        ),
                      // ─── 新增按钮 ───
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                        child: SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: _showAddAgentSheet,
                            icon: const Icon(Icons.add, size: 18),
                            label: const Text('注册新智能体'),
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

  Widget _buildSectionHeader(String title, String pos, {int? count}) {
    final isCollapsed = _collapsed.contains(title);
    final label = count != null ? '$title ($count)' : title;
    return Container(
      padding: EdgeInsets.fromLTRB(16, pos == 'top' ? 4 : 16, 16, 4),
      color: Theme.of(context).brightness == Brightness.dark ? const Color(0xFF1A1A1A) : const Color(0xFFF7F7F7),
      child: GestureDetector(
        onTap: () => _toggleSection(title),
        behavior: HitTestBehavior.opaque,
        child: Row(
          children: [
            Icon(
              isCollapsed ? Icons.chevron_right : Icons.expand_more,
              size: 16,
              color: Colors.grey[400],
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(color: Colors.grey[500], fontSize: 12, fontWeight: FontWeight.w500),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAgentTile(Agent a) {
    final uid = api.currentUser?.id ?? '';
    // 用户间私聊用双向session ID，确保双方看到同一会话
    final sessionId = a.type == 'user'
        ? (uid.compareTo(a.agentId) < 0
            ? 'session_user_${uid}_${a.agentId}'
            : 'session_user_${a.agentId}_${uid}')
        : 'session_agent_${a.agentId}';
    final name = a.showName;
    final color = Color(a.avatarColor);
    final avatarChar = a.avatar.isNotEmpty ? a.avatar : _agentAvatar(a.agentId);

    // 能力标签（最多显示3个）
    final caps = a.capabilities.split(',').where((c) => c.trim().isNotEmpty).toList();
    final displayCaps = caps.take(3).join(', ');
    final hasMoreCaps = caps.length > 3;

    return InkWell(
      onTap: () async {
        // 进入聊天
        final changed = await Navigator.push(context, MaterialPageRoute(
          builder: (_) => ChatDetail(
            agentId: a.agentId,
            agentName: name,
            agentColor: color,
            agentAvatar: avatarChar,
            sessionId: sessionId,
            agentStatus: a.status,
          ),
        ));
        if (changed == true) _loadAgents();
      },
      onLongPress: () => _openSettings(a),
      child: Container(
        color: Theme.of(context).cardColor,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(
          children: [
            Stack(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: color,
                  child: Text(
                    avatarChar,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 18),
                  ),
                ),
                if (a.online)
                  Positioned(
                    right: 0, bottom: 0,
                    child: Container(
                      width: 10, height: 10,
                      decoration: BoxDecoration(
                        color: const Color(0xFF07C160),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 第一行：名称 + 备注
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          name,
                          style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 16, color: Color(0xFF191919)),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (a.nickname.isNotEmpty) ...[
                        const SizedBox(width: 6),
                        Text(
                          '@${a.displayName}',
                          style: TextStyle(color: Colors.grey[400], fontSize: 12),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  // 第二行：能力标签 + 连接方式
                  Row(
                    children: [
                      // 能力标签
                      if (displayCaps.isNotEmpty) ...[
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                          decoration: BoxDecoration(
                            color: const Color(0xFFE8F4FD),
                            borderRadius: BorderRadius.circular(3),
                          ),
                          child: Text(
                            displayCaps + (hasMoreCaps ? '...' : ''),
                            style: const TextStyle(color: Color(0xFF2980B9), fontSize: 10),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 6),
                      ],
                      // 连接方式标签
                      if (a.connectionType.isNotEmpty && a.type != 'user') ...[
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                          decoration: BoxDecoration(
                            color: a.connectionType == 'local'
                                ? const Color(0xFFE8F4FD)
                                : a.connectionType == 'ssh'
                                    ? const Color(0xFFFEF3E2)
                                    : const Color(0xFFE8F8F5),
                            borderRadius: BorderRadius.circular(3),
                          ),
                          child: Text(
                            a.connectionTypeLabel,
                            style: TextStyle(
                              color: a.connectionType == 'local'
                                  ? const Color(0xFF2980B9)
                                  : a.connectionType == 'ssh'
                                      ? const Color(0xFFD35400)
                                      : const Color(0xFF1ABC9C),
                              fontSize: 10,
                            ),
                          ),
                        ),
                      ],
                      const Spacer(),
                      // 状态文本
                      Text(
                        _statusLabel(a.status),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: Colors.grey[500], fontSize: 12),
                      ),
                    ],
                  ),
                  // 第三行：连接地址（仅SSH显示）
                  if (a.connectionInfo.isNotEmpty && a.connectionType == 'ssh') ...[
                    const SizedBox(height: 2),
                    Text(
                      a.connectionInfo,
                      style: TextStyle(color: Colors.grey[400], fontSize: 10),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: Colors.grey[300], size: 20),
          ],
        ),
      ),
    );
  }

  void _openSettings(Agent a) async {
    final changed = await Navigator.push(context, MaterialPageRoute(
      builder: (_) => AgentSettingsScreen(agent: a),
    ));
    if (changed == true) _loadAgents();
  }

  /// 弹出注册智能体表单
  void _showAddAgentSheet() {
    final idCtrl = TextEditingController();
    final nameCtrl = TextEditingController();
    final capCtrl = TextEditingController();
    final hostCtrl = TextEditingController();
    final portCtrl = TextEditingController();
    final userCtrl = TextEditingController();
    final cmdCtrl = TextEditingController();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        String connType = 'local';
        bool saving = false;

        return StatefulBuilder(
          builder: (ctx, setSheetState) {
            final screenHeight = MediaQuery.of(ctx).size.height;
            return SizedBox(
              height: screenHeight * 0.75,
              child: Padding(
                padding: EdgeInsets.only(
                  left: 20, right: 20, top: 20,
                  bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
                ),
                child: Column(
                  children: [
                    // 标题栏
                    Row(
                      children: [
                        Icon(Icons.add_circle_outline, color: Theme.of(context).colorScheme.primary),
                        const SizedBox(width: 8),
                        const Text('注册新智能体', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                        const Spacer(),
                        IconButton(
                          icon: const Icon(Icons.close),
                          onPressed: () => Navigator.pop(ctx),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    // 可滚动表单区域
                    Expanded(
                      child: SingleChildScrollView(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                          // ID
                          TextField(
                            controller: idCtrl,
                            decoration: const InputDecoration(
                              labelText: 'ID（唯一标识，如 xiao-hong）',
                              border: OutlineInputBorder(),
                              isDense: true,
                              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                            ),
                          ),
                          const SizedBox(height: 12),
                          // 名称
                          TextField(
                            controller: nameCtrl,
                            decoration: const InputDecoration(
                              labelText: '名称（显示用，如 小红）',
                              border: OutlineInputBorder(),
                              isDense: true,
                              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                            ),
                          ),
                          const SizedBox(height: 12),
                          // 能力
                          TextField(
                            controller: capCtrl,
                            decoration: const InputDecoration(
                              labelText: '能力（逗号分隔，如 chat,code）',
                              border: OutlineInputBorder(),
                              isDense: true,
                              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                            ),
                          ),
                          const SizedBox(height: 16),
                          // 连接方式
                          const Text('连接方式', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.grey)),
                          const SizedBox(height: 8),
                          SegmentedButton<String>(
                            segments: const [
                              ButtonSegment(value: 'local', label: Text('本机'), icon: Icon(Icons.computer, size: 16)),
                              ButtonSegment(value: 'ssh', label: Text('SSH'), icon: Icon(Icons.dns, size: 16)),
                            ],
                            selected: {connType},
                            onSelectionChanged: (s) => setSheetState(() => connType = s.first),
                          ),
                          if (connType == 'ssh') ...[
                            const SizedBox(height: 12),
                            TextField(
                              controller: hostCtrl,
                              decoration: const InputDecoration(
                                labelText: 'IP 地址',
                                border: OutlineInputBorder(),
                                isDense: true,
                                contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                              ),
                            ),
                            const SizedBox(height: 12),
                            Row(
                              children: [
                                Expanded(
                                  child: TextField(
                                    controller: portCtrl,
                                    keyboardType: TextInputType.number,
                                    decoration: const InputDecoration(
                                      labelText: '端口',
                                      border: OutlineInputBorder(),
                                      isDense: true,
                                      contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: TextField(
                                    controller: userCtrl,
                                    decoration: const InputDecoration(
                                      labelText: 'SSH 用户',
                                      border: OutlineInputBorder(),
                                      isDense: true,
                                      contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            TextField(
                              controller: cmdCtrl,
                              decoration: const InputDecoration(
                                labelText: '命令模板（可选）',
                                hintText: "hermes -z '{task}' --yolo",
                                border: OutlineInputBorder(),
                                isDense: true,
                                contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                              ),
                            ),
                          ],
                          const SizedBox(height: 20),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  // 注册按钮（固定在底部）
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton(
                      onPressed: saving
                          ? null
                          : () async {
                              final id = idCtrl.text.trim();
                              final name = nameCtrl.text.trim();
                              if (id.isEmpty || name.isEmpty) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('ID 和名称不能为空')),
                                );
                                return;
                              }
                              setSheetState(() => saving = true);
                              final Map<String, dynamic> body = {
                                'id': id,
                                'name': name,
                                'capabilities': capCtrl.text.trim(),
                                'connection_type': connType,
                              };
                              if (connType == 'ssh') {
                                body['host'] = hostCtrl.text.trim();
                                body['port'] = int.tryParse(portCtrl.text.trim());
                                body['ssh_user'] = userCtrl.text.trim().isNotEmpty ? userCtrl.text.trim() : null;
                                body['command_template'] = cmdCtrl.text.trim().isNotEmpty ? cmdCtrl.text.trim() : null;
                              }
                              final result = await api.registerAgent(body);
                              setSheetState(() => saving = false);
                              if (ctx.mounted) Navigator.pop(ctx);
                              if (mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text(result['ok'] ? '✅ 注册成功' : '❌ ${result['message']}'),
                                  ),
                                );
                                if (result['ok']) _loadAgents();
                              }
                            },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Theme.of(context).colorScheme.primary,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: saving
                          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('注册', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ],
              ),
              ),
            );
          },
        );
      },
    );
  }
}
