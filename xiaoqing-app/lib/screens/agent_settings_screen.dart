import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../main.dart' show api;
import '../models/agent.dart';

/// 智能体设置页 — 自定义备注名 + 头像颜色
class AgentSettingsScreen extends StatefulWidget {
  final Agent agent;

  const AgentSettingsScreen({super.key, required this.agent});

  @override
  State<AgentSettingsScreen> createState() => _AgentSettingsScreenState();
}

class _AgentSettingsScreenState extends State<AgentSettingsScreen> {
  late TextEditingController _nicknameCtrl;
  late TextEditingController _capCtrl;
  late int _selectedColor;
  late bool _pinned;
  bool _saving = false;
  bool _saved = false;

  // 可选头像颜色（微信风格色系）
  static const List<int> _colorOptions = [
    0xFF07C160, // 微信绿
    0xFF3498db, // 蓝
    0xFFe74c3c, // 红
    0xFFe67e22, // 橙
    0xFF9b59b6, // 紫
    0xFF1abc9c, // 青
    0xFFf39c12, // 黄
    0xFF2c3e50, // 深蓝
    0xFFe84393, // 粉
    0xFF636e72, // 灰
  ];

  @override
  void initState() {
    super.initState();
    _nicknameCtrl = TextEditingController(text: widget.agent.nickname);
    _capCtrl = TextEditingController(text: widget.agent.capabilities);
    _selectedColor = widget.agent.avatarColor;
    _pinned = widget.agent.pinned;
  }

  @override
  void dispose() {
    _nicknameCtrl.dispose();
    _capCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    final ok = await api.updateAgentSettings(widget.agent.agentId, {
      'nickname': _nicknameCtrl.text.trim(),
      'avatar_color': _selectedColor,
      'pinned': _pinned,
      'capabilities': _capCtrl.text.trim(),
    });
    if (mounted) {
      setState(() { _saving = false; _saved = ok; });
      if (ok) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('✅ 设置已保存'), duration: Duration(seconds: 2)),
        );
        Future.delayed(const Duration(milliseconds: 500), () => Navigator.pop(context, true));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('❌ 保存失败'), duration: Duration(seconds: 2)),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.agent;
    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text('智能体设置', style: TextStyle(fontSize: 17)),
        centerTitle: true,
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 0.5,
      ),
      body: Column(
        children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
          // ── 预览头像 ──
          Center(
            child: Column(
              children: [
                CircleAvatar(
                  backgroundColor: Color(_selectedColor),
                  radius: 40,
                  child: Text(
                    widget.agent.avatar,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 28),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _nicknameCtrl.text.trim().isNotEmpty
                      ? _nicknameCtrl.text.trim()
                      : a.displayName,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF191919)),
                ),
                Text(
                  '@${a.agentId}',
                  style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // ── 备注名 ──
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
                  child: Text('备注名', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: TextField(
                    controller: _nicknameCtrl,
                    style: const TextStyle(fontSize: 16, color: Color(0xFF191919)),
                    decoration: InputDecoration(
                      hintText: a.displayName,
                      hintStyle: TextStyle(color: Colors.grey[400]),
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.zero,
                      suffixIcon: _nicknameCtrl.text.isNotEmpty
                          ? IconButton(
                              icon: Icon(Icons.clear, size: 18, color: Colors.grey[400]),
                              onPressed: () => _nicknameCtrl.clear(),
                            )
                          : null,
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── 选择头像颜色 ──
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('头像颜色', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: _colorOptions.map((c) {
                    final isSelected = c == _selectedColor;
                    return GestureDetector(
                      onTap: () => setState(() => _selectedColor = c),
                      child: Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: Color(c),
                          shape: BoxShape.circle,
                          border: isSelected
                              ? Border.all(color: Colors.white, width: 3)
                              : null,
                          boxShadow: isSelected
                              ? [BoxShadow(color: Color(c).withOpacity(0.5), blurRadius: 8, spreadRadius: 1)]
                              : null,
                        ),
                        child: isSelected
                            ? const Center(child: Icon(Icons.check, color: Colors.white, size: 20))
                            : null,
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── 置顶开关 ──
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(10),
            ),
            child: SwitchListTile(
              title: Row(
                children: [
                  Icon(Icons.push_pin, size: 18, color: _pinned ? const Color(0xFF07C160) : Colors.grey[400]),
                  const SizedBox(width: 8),
                  const Text('置顶联系人', style: TextStyle(fontSize: 15, color: Color(0xFF191919))),
                ],
              ),
              subtitle: Text(
                '置顶后显示在列表靠前位置',
                style: TextStyle(fontSize: 12, color: Colors.grey[400]),
              ),
              value: _pinned,
              activeColor: const Color(0xFF07C160),
              onChanged: (v) => setState(() => _pinned = v),
            ),
          ),

          const SizedBox(height: 16),

          // ── 能力编辑 ──
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.auto_fix_high, size: 18, color: Colors.grey[600]),
                    const SizedBox(width: 6),
                    Text('能力模块', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                  ],
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _capCtrl,
                  style: const TextStyle(fontSize: 15, color: Color(0xFF191919)),
                  decoration: InputDecoration(
                    hintText: 'chat, code, image, search,...',
                    hintStyle: TextStyle(color: Colors.grey[400]),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    isDense: true,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '逗号分隔，如 chat,code,image,search',
                  style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                ),
              ],
            ),
          ),

          const SizedBox(height: 32),

            ],
          ),
        ),
          // ── 保存按钮（固定底部）──
          Padding(
            padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.of(context).padding.bottom + 16),
            child: SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                onPressed: _saving ? null : _save,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF07C160),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  elevation: 0,
                ),
                child: _saving
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('保存', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
