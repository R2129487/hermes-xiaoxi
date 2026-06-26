import 'package:flutter/material.dart';
import '../services/dispatcher_api.dart';
import '../main.dart' show themeNotifier, api;
import '../models/user.dart';
import 'login_screen.dart';

/// 设置页面
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _hostCtrl = TextEditingController(text: '192.168.1.6');
  final _portCtrl = TextEditingController(text: '8767');
  bool _connected = false;
  bool _checking = false;

  @override
  void initState() {
    super.initState();
    _checkConnection();
  }

  @override
  void dispose() {
    _hostCtrl.dispose();
    _portCtrl.dispose();
    super.dispose();
  }

  Future<void> _checkConnection() async {
    setState(() => _checking = true);
    _connected = await api.checkConnection();
    if (mounted) setState(() => _checking = false);
  }

  Future<void> _connect() async {
    final host = _hostCtrl.text.trim();
    final port = int.tryParse(_portCtrl.text.trim()) ?? 8767;
    api.setServer(host, port);
    await _checkConnection();
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('退出登录'),
        content: const Text('确定要退出登录吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('退出'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await api.logout();
      if (mounted) {
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => LoginScreen(api: api)),
          (_) => false,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 连接状态卡片
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('服务器连接', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Icon(
                        _checking ? Icons.hourglass_empty : (_connected ? Icons.check_circle : Icons.error),
                        color: _checking ? Colors.grey : (_connected ? Colors.green : Colors.red),
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _checking ? '检测中...' : (_connected ? '已连接' : '未连接'),
                        style: TextStyle(color: _checking ? Colors.grey : (_connected ? Colors.green : Colors.red)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        flex: 3,
                        child: TextField(
                          controller: _hostCtrl,
                          decoration: const InputDecoration(
                            labelText: '服务器地址',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        flex: 1,
                        child: TextField(
                          controller: _portCtrl,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: '端口',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                            isDense: true,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    children: [
                      actionChip('本机', '192.168.1.6', '8767'),
                      actionChip('阿里云', '101.37.231.143', '8767'),
                    ],
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _connect,
                      icon: const Icon(Icons.link, size: 18),
                      label: const Text('连接'),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          // 暗色模式开关
          Card(
            child: SwitchListTile(
              secondary: Icon(
                themeNotifier.value == ThemeMode.dark ? Icons.dark_mode : Icons.light_mode,
                color: themeNotifier.value == ThemeMode.dark
                    ? const Color(0xFF1A73E8)
                    : Colors.grey[600],
              ),
              title: const Text('暗色模式', style: TextStyle(fontSize: 15)),
              subtitle: const Text('晚上关灯用，黑底白字不刺眼', style: TextStyle(fontSize: 12)),
              value: themeNotifier.value == ThemeMode.dark,
              activeColor: const Color(0xFF1A73E8),
              onChanged: (v) {
                themeNotifier.value = v ? ThemeMode.dark : ThemeMode.light;
              },
            ),
          ),
          const SizedBox(height: 16),
          // 用户管理（仅 admin 可见）
          if (api.currentUser?.role == 'admin')
            Card(
              child: ListTile(
                leading: Icon(Icons.people, color: Colors.grey[600]),
                title: const Text('用户管理', style: TextStyle(fontSize: 15)),
                subtitle: const Text('查看和管理所有用户', style: TextStyle(fontSize: 12)),
                trailing: Icon(Icons.chevron_right, color: Colors.grey[400]),
                onTap: () async {
                  final changed = await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => _UserManagementScreen(api: api)),
                  );
                  if (changed == true) setState(() {});
                },
              ),
            ),
          if (api.currentUser?.role == 'admin') const SizedBox(height: 16),
          // 退出登录按钮
          Card(
            child: ListTile(
              leading: Icon(Icons.logout, color: Colors.red[400]),
              title: const Text('退出登录', style: TextStyle(color: Colors.red, fontSize: 15)),
              trailing: const Icon(Icons.chevron_right),
              onTap: _logout,
            ),
          ),
          const SizedBox(height: 16),
          // 关于卡片
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('关于小希', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF191919))),
                  const SizedBox(height: 8),
                  Text(
                    '小希 App — 智能体多端消息管理平台。\n'
                    '连接调度器，统一管理多台智能体，'
                    '支持聊天、联系人分组、服务器管理。',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600], height: 1.5),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Icon(Icons.info_outline, size: 14, color: Colors.grey[400]),
                      const SizedBox(width: 6),
                      Text(
                        '版本: v2.1.0',
                        style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      );
  }

  Widget actionChip(String label, String host, String port) {
    return ActionChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      onPressed: () {
        _hostCtrl.text = host;
        _portCtrl.text = port;
      },
    );
  }
}

/// 用户管理页面 — 仅 admin 可用
class _UserManagementScreen extends StatefulWidget {
  final DispatcherApi api;
  const _UserManagementScreen({required this.api});

  @override
  State<_UserManagementScreen> createState() => _UserManagementScreenState();
}

class _UserManagementScreenState extends State<_UserManagementScreen> {
  DispatcherApi get _api => widget.api;
  List<User> _users = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadUsers();
  }

  Future<void> _loadUsers() async {
    setState(() => _loading = true);
    final users = await _api.getUsers();
    if (mounted) setState(() { _users = users; _loading = false; });
  }

  String _roleLabel(String role) {
    switch (role) {
      case 'admin': return '管理员';
      case 'operator': return '操作员';
      case 'observer': return '观察员';
      default: return role;
    }
  }

  Color _roleColor(String role) {
    switch (role) {
      case 'admin': return Colors.red;
      case 'operator': return Colors.blue;
      case 'observer': return Colors.grey;
      default: return Colors.grey;
    }
  }

  void _showRolePicker(User user) async {
    final currentRole = user.role;
    final newRole = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text('修改 ${user.displayName} 的角色'),
        children: ['operator', 'observer', 'admin'].map<Widget>((r) {
          return SimpleDialogOption(
            child: Row(
              children: [
                Icon(Icons.check, size: 16,
                    color: r == currentRole ? Colors.green : Colors.transparent),
                const SizedBox(width: 8),
                Text('${_roleLabel(r)}${r == currentRole ? '（当前）' : ''}'),
              ],
            ),
            onPressed: () => Navigator.pop(ctx, r == currentRole ? null : r),
          );
        }).toList(),
      ),
    );
    if (newRole != null && mounted) {
      final ok = await _api.updateUser(user.id, {'role': newRole});
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ok ? '✅ 已更新角色' : '❌ 更新失败')),
        );
        if (ok) _loadUsers();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      appBar: AppBar(title: const Text('用户管理')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadUsers,
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _users.length,
                itemBuilder: (_, i) {
                  final u = _users[i];
                  return Card(
                    child: ListTile(
                      leading: CircleAvatar(
                        backgroundColor: _roleColor(u.role),
                        child: Text(
                          u.displayName.isNotEmpty ? u.displayName[0] : u.username[0],
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                        ),
                      ),
                      title: Text(u.displayName.isNotEmpty ? u.displayName : u.username),
                      subtitle: Text('@${u.username} · ${_roleLabel(u.role)}'),
                      trailing: u.id != _api.currentUser?.id
                          ? IconButton(
                              icon: Icon(Icons.admin_panel_settings, color: Colors.grey[400]),
                              onPressed: () => _showRolePicker(u),
                            )
                          : const Chip(label: Text('自己', style: TextStyle(fontSize: 11))),
                    ),
                  );
                },
              ),
            ),
    );
  }
}
