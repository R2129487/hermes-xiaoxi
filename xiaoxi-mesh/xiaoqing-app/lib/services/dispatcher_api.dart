import 'dart:convert';
import 'dart:math';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/message.dart';
import '../models/agent.dart';
import '../models/user.dart';

/// 调度器 HTTP API 客户端
/// 管理 JWT token 的获取/存储/刷新，所有请求自动携带 Authorization header
/// 所有 HTTP 请求带自动重试（连接失败时重试最多 3 次，指数退避）
class DispatcherApi {
  String _host = '192.168.1.6';
  int _port = 8767;
  String? _token;
  User? _currentUser;

  String get baseUrl => 'http://$_host:$_port';
  bool get isLoggedIn => _token != null;
  User? get currentUser => _currentUser;
  String get host => _host;
  int get port => _port;

  void setServer(String host, int port) {
    _host = host;
    _port = port;
    _saveServerAddress(host, port);
  }

  Future<void> _saveServerAddress(String host, int port) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_host', host);
    await prefs.setInt('server_port', port);
  }

  Future<void> _loadServerAddress() async {
    final prefs = await SharedPreferences.getInstance();
    _host = prefs.getString('server_host') ?? '192.168.1.6';
    _port = prefs.getInt('server_port') ?? 8767;
  }

  // ── 带重试的 HTTP 辅助方法 ──

  Future<http.Response> _get(String path, {int retries = 3, Duration timeout = const Duration(seconds: 5)}) =>
      _retry(() => http.get(Uri.parse('$baseUrl$path'), headers: _headersWithAuth()).timeout(timeout), retries);

  Future<http.Response> _post(String path, dynamic body, {int retries = 3, Duration timeout = const Duration(seconds: 30)}) =>
      _retry(() => http.post(
        Uri.parse('$baseUrl$path'),
        headers: _headersWithAuth(extra: {'Content-Type': 'application/json'}),
        body: json.encode(body),
      ).timeout(timeout), retries);

  Future<http.Response> _put(String path, dynamic body, {int retries = 3, Duration timeout = const Duration(seconds: 5)}) =>
      _retry(() => http.put(
        Uri.parse('$baseUrl$path'),
        headers: _headersWithAuth(extra: {'Content-Type': 'application/json'}),
        body: json.encode(body),
      ).timeout(timeout), retries);

  Future<http.Response> _delete(String path, {int retries = 3, Duration timeout = const Duration(seconds: 5)}) =>
      _retry(() => http.delete(Uri.parse('$baseUrl$path'), headers: _headersWithAuth()).timeout(timeout), retries);

  Future<http.Response> _retry(Future<http.Response> Function() fn, int maxRetries) async {
    for (int i = 0; i <= maxRetries; i++) {
      try {
        return await fn();
      } catch (e) {
        if (i >= maxRetries) rethrow;
        await Future.delayed(Duration(seconds: pow(2, i).toInt()));
      }
    }
    throw Exception('重试耗尽');
  }

  // ==================== Token 管理 ====================

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('jwt_token');
    _loadServerAddress();
  }

  Map<String, String> _headersWithAuth({Map<String, String>? extra}) {
    final headers = <String, String>{
      if (_token != null) 'Authorization': 'Bearer $_token',
      ...?extra,
    };
    return headers;
  }

  Future<void> _saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('jwt_token', token);
  }

  Future<void> clearToken() async {
    _token = null;
    _currentUser = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('jwt_token');
  }

  // ==================== 认证 API ====================

  Future<Map<String, dynamic>> login(String username, String password) async {
    try {
      final r = await _post('/api/auth/login', {'username': username, 'password': password}, retries: 0);
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

  Future<Map<String, dynamic>> register(String username, String password, {String? displayName, String? role}) async {
    try {
      final r = await _post('/api/auth/register', {
        'username': username,
        'password': password,
        if (displayName != null) 'display_name': displayName,
        if (role != null) 'role': role,
      }, retries: 0);
      final data = json.decode(r.body);
      if (data['code'] == 0) {
        return {'ok': true, 'message': data['message'] ?? '注册成功'};
      }
      return {'ok': false, 'message': data['message'] ?? '注册失败'};
    } catch (e) {
      return {'ok': false, 'message': '连接失败: $e'};
    }
  }

  Future<bool> getMe() async {
    if (_token == null) return false;
    try {
      final r = await _get('/api/auth/me', timeout: const Duration(seconds: 5));
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

  Future<void> logout() async {
    await clearToken();
  }

  // ==================== 用户管理 API ====================

  Future<List<User>> getUsers() async {
    try {
      final r = await _get('/api/auth/users');
      if (r.statusCode != 200) return [];
      final data = json.decode(r.body);
      if (data['code'] != 0) return [];
      return (data['data'] as List).map((u) => User.fromJson(u)).toList();
    } catch (_) {
      return [];
    }
  }

  Future<bool> updateUser(String userId, Map<String, dynamic> updates) async {
    try {
      final r = await _put('/api/auth/users/$userId', updates);
      if (r.statusCode != 200) return false;
      final data = json.decode(r.body);
      return data['code'] == 0;
    } catch (_) {
      return false;
    }
  }

  Future<bool> deleteUser(String userId) async {
    try {
      final r = await _delete('/api/auth/users/$userId');
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ==================== 智能体 API ====================

  Future<List<Agent>> getAgents() async {
    try {
      final r = await _get('/api/chat/agents');
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
        online: a['status'] != 'offline',
        status: a['status'] ?? 'offline',
        pinned: a['pinned'] ?? false,
        capabilities: a['capabilities'] ?? '',
      )).toList();
    } catch (_) {
      return [];
    }
  }

  Future<List<Map<String, dynamic>>> getSessions() async {
    try {
      final r = await _get('/api/chat/sessions');
      if (r.statusCode != 200) return [];
      final data = json.decode(r.body);
      if (data['code'] != 0) return [];
      return List<Map<String, dynamic>>.from(data['data']);
    } catch (_) {
      return [];
    }
  }

  /// 解析时间戳：兼容旧UTC格式和新北京时间格式
  DateTime _parseTimestamp(String ts) {
    if (ts.isEmpty) return DateTime.now();
    // 旧格式 "2026-06-29 03:43:56" 是UTC，需+8小时
    // 新格式 "2026-06-29T11:47:27" 已是北京时间
    final fixed = ts.replaceAll(' ', 'T');
    final dt = DateTime.tryParse(fixed);
    if (dt == null) return DateTime.now();
    // 沀时区信息 + 小时<12 → 大概率是旧UTC数据，加8小时
    if (!ts.contains('+') && !ts.endsWith('Z') && dt.hour < 12) {
      return dt.add(const Duration(hours: 8));
    }
    return dt;
  }

  Future<List<Message>> getHistory(String sessionId) async {
    try {
      final r = await _get('/api/chat/history/${Uri.encodeComponent(sessionId)}');
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
          timestamp: _parseTimestamp(m['timestamp'] ?? ''),
          isMe: isUser,
        );
      }).toList();
    } catch (_) {
      return [];
    }
  }

  Future<Map<String, dynamic>?> sendMessage(String text, String sessionId, String agentId) async {
    try {
      final r = await _post('/api/chat', {
        'message': text,
        'session_id': sessionId,
        'agent_id': agentId,
      }, timeout: const Duration(seconds: 10));
      if (r.statusCode != 200) return null;
      final data = json.decode(r.body);
      if (data['code'] != 0) return null;
      return data['data'];  // {task_id, status, detail}
    } catch (_) {
      return null;
    }
  }

  /// 轮询消息状态直到完成
  Future<String?> pollMessageReply(String taskId, {Duration interval = const Duration(seconds: 1), int maxTries = 30}) async {
    for (int i = 0; i < maxTries; i++) {
      try {
        final r = await _get('/api/chat/status/$taskId', timeout: const Duration(seconds: 3));
        if (r.statusCode != 200) { await Future.delayed(interval); continue; }
        final data = json.decode(r.body);
        if (data['code'] != 0) { await Future.delayed(interval); continue; }
        final task = data['data'];
        final status = task['status'] ?? '';
        final reply = task['reply'] ?? '';
        if (status == 'completed' && reply.isNotEmpty) return reply;
        if (status == 'failed') return '⚠️ ${task['detail'] ?? '处理失败'}';
      } catch (_) {}
      await Future.delayed(interval);
    }
    return '⏱️ 处理超时';
  }

  /// 查询消息任务状态
  Future<Map<String, dynamic>?> getTaskStatus(String taskId) async {
    try {
      final r = await _get('/api/chat/status/$taskId', timeout: const Duration(seconds: 3));
      if (r.statusCode != 200) return null;
      final data = json.decode(r.body);
      if (data['code'] != 0) return null;
      return data['data'] as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>?> uploadFile(List<int> bytes, String filename) async {
    try {
      final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/chat/upload'));
      if (_token != null) {
        request.headers['Authorization'] = 'Bearer $_token';
      }
      request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
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

  Future<bool> checkConnection() async {
    try {
      final r = await _get('/api/status', timeout: const Duration(seconds: 3));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> deleteSession(String sessionId) async {
    try {
      final r = await _delete('/api/chat/session/${Uri.encodeComponent(sessionId)}');
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>> registerAgent(Map<String, dynamic> data) async {
    try {
      final r = await _post('/api/agents', data, timeout: const Duration(seconds: 5));
      final d = json.decode(r.body);
      return {'ok': d['code'] == 0, 'message': d['message'] ?? '注册成功'};
    } catch (e) {
      return {'ok': false, 'message': '连接失败: $e'};
    }
  }

  Future<bool> deleteAgent(String agentId) async {
    try {
      final r = await _delete('/api/agents/$agentId');
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> updateAgentSettings(String agentId, Map<String, dynamic> settings) async {
    try {
      final r = await _post('/api/chat/agents/$agentId/settings', settings, timeout: const Duration(seconds: 5));
      if (r.statusCode != 200) return false;
      final data = json.decode(r.body);
      return data['code'] == 0;
    } catch (_) {
      return false;
    }
  }
}
