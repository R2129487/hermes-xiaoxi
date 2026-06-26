import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/message.dart';
import '../models/agent.dart';

/// 调度器 HTTP API 客户端
/// 替代原来的 MESH WebSocket 连接
class DispatcherApi {
  String _host = '192.168.1.6';
  int _port = 8767;

  String get baseUrl => 'http://$_host:$_port';

  void setServer(String host, int port) {
    _host = host;
    _port = port;
  }

  /// 获取可用智能体列表
  Future<List<Agent>> getAgents() async {
    try {
      final r = await http.get(Uri.parse('$baseUrl/api/chat/agents'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode != 200) return [];
      final data = json.decode(r.body);
      if (data['code'] != 0) return [];
      final list = data['data'] as List;
      return list.map((a) => Agent(
        agentId: a['id'],
        displayName: a['name'],
        nickname: a['nickname'] ?? '',
        avatar: a['avatar'] ?? (a['name']?.toString().isNotEmpty == true ? a['name'][0] : '?'),
        avatarColor: a['avatar_color'] ?? 0xFF888888,
        online: a['status'] == 'online',
        pinned: a['pinned'] ?? false,
        capabilities: a['capabilities'] ?? '',
      )).toList();
    } catch (_) {
      return [];
    }
  }

  /// 获取会话列表
  Future<List<Map<String, dynamic>>> getSessions() async {
    try {
      final r = await http.get(Uri.parse('$baseUrl/api/chat/sessions'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode != 200) return [];
      final data = json.decode(r.body);
      if (data['code'] != 0) return [];
      return List<Map<String, dynamic>>.from(data['data']);
    } catch (_) {
      return [];
    }
  }

  /// 获取聊天历史
  Future<List<Message>> getHistory(String sessionId) async {
    try {
      final r = await http.get(
        Uri.parse('$baseUrl/api/chat/history/${Uri.encodeComponent(sessionId)}'),
      ).timeout(const Duration(seconds: 5));
      if (r.statusCode != 200) return [];
      final data = json.decode(r.body);
      if (data['code'] != 0) return [];
      final msgs = data['data']['messages'] as List;
      return msgs.map((m) {
        final isUser = m['role'] == 'user';
        return Message(
          id: DateTime.now().microsecondsSinceEpoch.toString(),
          content: m['content'] ?? '',
          fromAgent: isUser ? 'user' : 'assistant',
          toAgent: isUser ? 'assistant' : 'user',
          timestamp: DateTime.tryParse(m['timestamp'] ?? '') ?? DateTime.now(),
          isMe: isUser,
        );
      }).toList();
    } catch (_) {
      return [];
    }
  }

  /// 发送消息
  Future<String?> sendMessage(String text, String sessionId, String agentId) async {
    try {
      final r = await http.post(
        Uri.parse('$baseUrl/api/chat'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'message': text,
          'session_id': sessionId,
          'agent_id': agentId,
        }),
      ).timeout(const Duration(seconds: 30));
      if (r.statusCode != 200) return null;
      final data = json.decode(r.body);
      if (data['code'] != 0) return null;
      return data['data']['reply'];
    } catch (_) {
      return null;
    }
  }

  /// 上传文件
  Future<Map<String, dynamic>?> uploadFile(List<int> bytes, String filename) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/api/chat/upload'),
      );
      request.files.add(http.MultipartFile.fromBytes(
        'file', bytes, filename: filename,
      ));
      final streamed = await request.send().timeout(const Duration(seconds: 30));
      final r = await http.Response.fromStream(streamed);
      if (r.statusCode != 200) return null;
      final data = json.decode(r.body);
      if (data['code'] != 0) return null;
      return data['data'];
    } catch (_) {
      return null;
    }
  }

  /// 检测连接状态
  Future<bool> checkConnection() async {
    try {
      final r = await http.get(Uri.parse('$baseUrl/api/status'))
          .timeout(const Duration(seconds: 3));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// 删除会话
  Future<bool> deleteSession(String sessionId) async {
    try {
      final r = await http.delete(
        Uri.parse('$baseUrl/api/chat/session/${Uri.encodeComponent(sessionId)}'),
      ).timeout(const Duration(seconds: 5));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// 注册新智能体
  Future<Map<String, dynamic>> registerAgent(Map<String, dynamic> data) async {
    try {
      final r = await http.post(
        Uri.parse('$baseUrl/api/agents'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode(data),
      ).timeout(const Duration(seconds: 5));
      final d = json.decode(r.body);
      return {'ok': d['code'] == 0, 'message': d['message'] ?? '注册成功'};
    } catch (e) {
      return {'ok': false, 'message': '连接失败: $e'};
    }
  }

  /// 删除智能体
  Future<bool> deleteAgent(String agentId) async {
    try {
      final r = await http.delete(
        Uri.parse('$baseUrl/api/agents/$agentId'),
      ).timeout(const Duration(seconds: 5));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// 更新智能体设置
  Future<bool> updateAgentSettings(String agentId, Map<String, dynamic> settings) async {
    try {
      final r = await http.post(
        Uri.parse('$baseUrl/api/chat/agents/$agentId/settings'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode(settings),
      ).timeout(const Duration(seconds: 5));
      if (r.statusCode != 200) return false;
      final data = json.decode(r.body);
      return data['code'] == 0;
    } catch (_) {
      return false;
    }
  }
}
