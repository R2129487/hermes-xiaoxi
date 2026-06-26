import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/message.dart';
import '../models/agent.dart';
import '../models/user.dart';

/// 调度器 HTTP API 客户端
/// 管理 JWT token 的获取/存储/刷新，所有请求自动携带 Authorization header
class DispatcherApi {
  String _host = '192.168.1.6';
  int _port = 8767;
  String? _token;
  User? _currentUser;

  String get baseUrl => 'http://$_host:$_port';
  bool get isLoggedIn => _token != null;
  User? get currentUser => _currentUser;

  void setServer(String host, int port) {
    _host = host;
    _port = port;
  }

  // ==================== Token 管理 ====================

  /// 从 SharedPreferences 加载 token
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('jwt_token');
  }

  /// 获取带 Authorization 的请求头
  Map<String, String> _headersWithAuth({Map<String, String>? extra}) {
    final headers = <String, String>{
      if (_token != null) 'Authorization': 'Bearer $_token',
      ...?extra,
    };
    return headers;
  }

  /// 存储 token 到内存和 SharedPreferences
  Future<void> _saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('jwt_token', token);
  }

  /// 清除 token
  Future<void> clearToken() async {
    _token = null;
    _currentUser = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('jwt_token');
  }

  // ==================== 认证 API ====================

  /// 登录 — 返回 token 和用户信息
  Future<Map<String, dynamic>> login(String username, String password) async {
    try {
      final r = await http.post(
        Uri.parse('$baseUrl/api/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'username': username, 'password': password}),
      ).timeout(const Duration(seconds: 10));

      final data = json.decode(r.body);
      if (data['code'] == 0) {
        final token = data['data']['token'] as String;
        await _saveToken(token);
        _currentUser = User.fromJson(data['data']['user']);
        return {'ok': true, 'user': _currentUser};
      }
      return {'ok': false, 'message': data['message'] ?? '登录失败'};
    } catch (e) {
      return {'ok': false, 'message': '连接失败: $e'};
    }
  }

  /// 注册
  Future<Map<String, dynamic>> register(String username, String password, {String? displayName, String? role}) async {
    try {
      final r = await http.post(
        Uri.parse('$baseUrl/api/auth/register'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'username': username,
          'password': password,
          if (displayName != null) 'display_name': displayName,
          if (role != null) 'role': role,
        }),
      ).timeout(const Duration(seconds: 10));

      final data = json.decode(r.body);
      if (data['code'] == 0) {
        return {'ok': true, 'message': data['message'] ?? '注册成功'};
      }
      return {'ok': false, 'message': data['message'] ?? '注册失败'};
    } catch (e) {
      return {'ok': false, 'message': '连接失败: $e'};
    }
  }

  /// 获取当前登录用户信息 — 用来验证 token 是否仍然有效
  Future<bool> getMe() async {
    if (_token == null) return false;
    try {
      final r = await http.get(
        Uri.parse('$baseUrl/api/auth/me'),
        headers: _headersWithAuth(),
      ).timeout(const Duration(seconds: 5));

      if (r.statusCode != 200) return false;
      final data = json.decode(r.body);
      if (data['code'] == 0) {
        _currentUser = User.fromJson(data['data']);
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  /// 退出登录
  Future<void> logout() async {
    await clearToken();
  }

  // ==================== 用户管理 API ====================

  /// 获取用户列表（仅 admin）
  Future<List<User>> getUsers() async {
    try {
      final r = await http.get(
        Uri.parse('$baseUrl/api/auth/users'),
        headers: _headersWithAuth(),
      ).timeout(const Duration(seconds: 5));
      if (r.statusCode != 200) return [];
      final data = json.decode(r.body);
      if (data['code'] != 0) return [];
      return (data['data'] as List).map((u) => User.fromJson(u)).toList();
    } catch (_) {
      return [];
    }
  }

  /// 修改用户角色/信息（仅 admin）
  Future<bool> updateUser(String userId, Map<String, dynamic> updates) async {
    try {
      final r = await http.put(
        Uri.parse('$baseUrl/api/auth/users/$userId'),
        headers: _headersWithAuth(extra: {'Content-Type': 'application/json'}),
        body: json.encode(updates),
      ).timeout(const Duration(seconds: 5));
      if (r.statusCode != 200) return false;
      final data = json.decode(r.body);
      return data['code'] == 0;
    } catch (_) {
      return false;
    }
  }

  /// 删除用户（仅 admin）
  Future<bool> deleteUser(String userId) async {
    try {
      final r = await http.delete(
        Uri.parse('$baseUrl/api/auth/users/$userId'),
        headers: _headersWithAuth(),
      ).timeout(const Duration(seconds: 5));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ==================== 智能体 API ====================

  /// 获取可用智能体列表
  Future<List<Agent>> getAgents() async {
    try {
      final r = await http.get(
        Uri.parse('$baseUrl/api/chat/agents'),
        headers: _headersWithAuth(),
      ).timeout(const Duration(seconds: 5));
      if (r.statusCode != 200) return [];
      final data = json.decode(r.body);
      if (data['code'] != 0) return [];
      final list = data['data'] as List;
      return list.map((a) => Agent(
        agentId: a['id'],
        displayName: a['name'],
        nickname: a['nickname'] ?? '',
        type: a['type'] ?? 'agent',
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
      final r = await http.get(
        Uri.parse('$baseUrl/api/chat/sessions'),
        headers: _headersWithAuth(),
      ).timeout(const Duration(seconds: 5));
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
        headers: _headersWithAuth(),
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
        headers: _headersWithAuth(extra: {'Content-Type': 'application/json'}),
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
      if (_token != null) {
        request.headers['Authorization'] = 'Bearer $_token';
      }
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
      final r = await http.get(
        Uri.parse('$baseUrl/api/status'),
        headers: _headersWithAuth(),
      ).timeout(const Duration(seconds: 3));
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
        headers: _headersWithAuth(),
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
        headers: _headersWithAuth(extra: {'Content-Type': 'application/json'}),
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
        headers: _headersWithAuth(),
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
        headers: _headersWithAuth(extra: {'Content-Type': 'application/json'}),
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
