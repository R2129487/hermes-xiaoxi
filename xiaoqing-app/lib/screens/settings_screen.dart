import 'package:flutter/material.dart';
import '../services/dispatcher_api.dart';
import '../main.dart';

/// 设置页面
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final DispatcherApi _api = DispatcherApi();
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
    _connected = await _api.checkConnection();
    if (mounted) setState(() => _checking = false);
  }

  Future<void> _connect() async {
    final host = _hostCtrl.text.trim();
    final port = int.tryParse(_portCtrl.text.trim()) ?? 8767;
    _api.setServer(host, port);
    await _checkConnection();
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
