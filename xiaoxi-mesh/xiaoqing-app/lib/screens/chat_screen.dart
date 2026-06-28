import 'package:flutter/material.dart';
import '../services/dispatcher_api.dart';
import '../models/agent.dart';
import '../models/message.dart';
import 'chat_detail.dart';
import '../main.dart' show api;

/// 对话列表 — 微信首页风格，每个智能体一个聊天框
class ConversationList extends StatefulWidget {
  const ConversationList({super.key});

  @override
  State<ConversationList> createState() => _ConversationListState();
}

class _ConversationListState extends State<ConversationList> {
  List<Agent> _agents = [];
  Map<String, List<Message>> _historyCache = {};
  bool _loading = true;
  final Set<String> _collapsed = {};  // 折叠的分栏 key

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
  void initState() {
    super.initState();
    _loadData();
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

  Future<void> _loadData() async {
    final agents = await api.getAgents();
    // 排序：调度员置顶 → 置顶 → 在线 → 离线
    agents.sort((a, b) {
      final w = a.sortWeight.compareTo(b.sortWeight);
      if (w != 0) return w;
      return a.showName.compareTo(b.showName);
    });

    final history = <String, List<Message>>{};
    for (final a in agents) {
      final sessionId = 'session_agent_${a.agentId}';
      final msgs = await api.getHistory(sessionId);
      history[a.agentId] = msgs;
    }
    if (mounted) {
      setState(() {
        _agents = agents;
        _historyCache = history;
        _loading = false;
      });
    }
  }

  String _formatTime(String? time) {
    if (time == null || time.isEmpty) return '';
    try {
      final dt = DateTime.parse(time);
      final now = DateTime.now();
      if (dt.day == now.day && dt.month == now.month && dt.year == now.year) {
        return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
      }
      return '${dt.month}/${dt.day}';
    } catch (_) {
      return '';
    }
  }

  // ─── 分组提取 ───
  bool _isSelf(Agent a) {
    final uid = api.currentUser?.id ?? '';
    return uid.isNotEmpty && a.agentId == 'user_$uid';
  }

  List<Agent> get _dispatchers => _agents.where((a) => a.type == 'dispatcher').toList();
  List<Agent> get _pinnedOnline =>
      _agents.where((a) => a.type == 'agent' && (a.pinned || a.online)).toList();
  List<Agent> get _users =>
      _agents.where((a) => a.type == 'user' && !_isSelf(a)).toList();
  List<Agent> get _offline =>
      _agents.where((a) => a.type == 'agent' && !a.pinned && !a.online).toList();

  Widget _buildSectionHeader(String title, {bool top = false, int? count}) {
    final isCollapsed = _collapsed.contains(title);
    final label = count != null ? '$title ($count)' : title;
    return Container(
      padding: EdgeInsets.fromLTRB(16, top ? 4 : 16, 16, 4),
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

  Widget _buildChatTile(Agent a) {
    final sessionId = 'session_agent_${a.agentId}';
    final msgs = _historyCache[a.agentId] ?? [];
    final lastMsg = msgs.isNotEmpty ? msgs.last.content : '';
    final lastTime = msgs.isNotEmpty ? msgs.last.timestamp.toIso8601String() : null;
    final msgCount = msgs.length;
    final name = a.showName;
    final color = Color(a.avatarColor);
    final avatarChar = a.avatar.isNotEmpty ? a.avatar : (a.displayName.isNotEmpty ? a.displayName[0] : '?');

    return InkWell(
      onTap: () {
        Navigator.push(context, MaterialPageRoute(
          builder: (_) => ChatDetail(
            agentId: a.agentId,
            agentName: name,
            agentColor: color,
            agentAvatar: avatarChar,
            sessionId: sessionId,
            agentStatus: a.status,
          ),
        )).then((_) => _loadData());
      },
      child: Container(
        color: Theme.of(context).cardColor,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            // 头像 + 在线状态
            Stack(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: color,
                  child: Text(
                    avatarChar,
                    style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.w600, fontSize: 18,
                    ),
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
            // 文字区域
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            name,
                            style: const TextStyle(
                              fontWeight: FontWeight.w500, fontSize: 16, color: Color(0xFF191919),
                            ),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            _statusLabel(a.status),
                            style: TextStyle(color: Colors.grey[400], fontSize: 11),
                          ),
                          if (a.pinned) ...[
                            const SizedBox(width: 4),
                            Icon(Icons.push_pin, size: 14, color: Colors.grey[400]),
                          ],
                        ],
                      ),
                      if (msgCount > 0)
                        Text(
                          _formatTime(lastTime),
                          style: TextStyle(color: Colors.grey[400], fontSize: 11),
                        ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    msgCount == 0
                        ? (a.online ? '在线 · 开始对话' : '离线')
                        : (lastMsg.length > 35 ? '${lastMsg.substring(0, 35)}...' : lastMsg),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: msgCount == 0 ? Colors.grey[400] : Colors.grey[500],
                      fontSize: 13,
                    ),
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
    return _loading
        ? const Center(child: CircularProgressIndicator())
        : RefreshIndicator(
            onRefresh: _loadData,
            child: _agents.isEmpty
                ? ListView(
                    children: [
                      SizedBox(height: MediaQuery.of(context).size.height * 0.25),
                      Center(
                        child: Column(
                          children: [
                            Icon(Icons.chat_bubble_outline, size: 64, color: Colors.grey[300]),
                            const SizedBox(height: 16),
                            Text('暂无智能体', style: TextStyle(color: Colors.grey[500], fontSize: 14)),
                          ],
                        ),
                      ),
                    ],
                  )
                : ListView(
                    padding: EdgeInsets.zero,
                    children: [
                      // ─── 调度员 ───
                      if (_dispatchers.isNotEmpty) ...[
                        _buildSectionHeader('调度员', top: true, count: _dispatchers.length),
                        if (!_collapsed.contains('调度员'))
                          ..._dispatchers.map((a) => _buildChatTile(a)),
                      ],
                      // ─── 用户 ───
                      if (_users.isNotEmpty) ...[
                        _buildSectionHeader('用户', count: _users.length),
                        if (!_collapsed.contains('用户'))
                          ..._users.map((a) => _buildChatTile(a)),
                      ],
                      // ─── 在线 / 置顶 ───
                      if (_pinnedOnline.isNotEmpty) ...[
                        _buildSectionHeader('智能体', count: _pinnedOnline.length),
                        if (!_collapsed.contains('智能体'))
                          ..._pinnedOnline.map((a) => _buildChatTile(a)),
                      ],
                      // ─── 离线 ───
                      if (_offline.isNotEmpty) ...[
                        _buildSectionHeader('离线', count: _offline.length),
                        if (!_collapsed.contains('离线'))
                          ..._offline.map((a) => _buildChatTile(a)),
                      ],
                      const SizedBox(height: 20),
                    ],
                  ),
          );
  }
}
