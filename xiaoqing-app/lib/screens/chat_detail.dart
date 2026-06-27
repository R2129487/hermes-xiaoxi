import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import '../services/dispatcher_api.dart';
import '../services/voice_service.dart';
import '../models/message.dart';
import '../main.dart' show api;

/// 聊天详情页 — 微信风格消息气泡 + 输入框
class ChatDetail extends StatefulWidget {
  final String agentId;
  final String agentName;
  final Color agentColor;
  final String agentAvatar;
  final String sessionId;
  final String agentStatus;  // online/offline/thinking/working/idle

  const ChatDetail({
    super.key,
    required this.agentId,
    required this.agentName,
    required this.agentColor,
    required this.agentAvatar,
    required this.sessionId,
    this.agentStatus = 'offline',
  });

  @override
  State<ChatDetail> createState() => _ChatDetailState();
}

class _ChatDetailState extends State<ChatDetail> {
  final TextEditingController _textCtrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();
  final FocusNode _focusNode = FocusNode();
  List<Message> _messages = [];
  bool _loading = true;
  bool _sending = false;

  /// 顶部实时状态（在线/正在回复...），默认用传入的状态
  String _headerStatus = '';

  // 语音识别（sherpa-onnx 本地离线，点按录音→填输入框→手动发）
  final VoiceService _voice = VoiceService();
  final AudioRecorder _recorder = AudioRecorder();
  bool _isRecording = false;
  bool _voiceReady = false;
  String? _recordPath;

  @override
  void initState() {
    super.initState();
    _headerStatus = widget.agentStatus;
    _loadHistory();
    _textCtrl.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _textCtrl.dispose();
    _scrollCtrl.dispose();
    _focusNode.dispose();
    _voice.dispose();
    super.dispose();
  }

  Future<void> _loadHistory() async {
    final msgs = await api.getHistory(widget.sessionId);
    if (mounted) {
      setState(() { _messages = msgs; _loading = false; });
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    }
  }

  void _scrollToBottom() {
    if (_scrollCtrl.hasClients) {
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    }
  }

  // ========== 发送纯文本 ==========

  /// 消息ID → 状态文字
  final Map<String, String> _msgStatus = {};

  Future<void> _sendMessage({String? text}) async {
    final msg = text ?? _textCtrl.text.trim();
    if (msg.isEmpty || _sending) return;

    _textCtrl.clear();
    final msgId = DateTime.now().microsecondsSinceEpoch.toString();
    _msgStatus[msgId] = '📤 已发出';
    setState(() {
      _sending = true;
      _messages.add(Message(
        id: msgId,
        content: msg,
        fromAgent: 'user',
        toAgent: widget.agentId,
        isMe: true,
      ));
    });
    _scrollToBottom();

    // 异步发送，立即返回 task_id
    final result = await api.sendMessage(msg, widget.sessionId, widget.agentId);
    final taskId = result?['task_id'] as String?;
    final status = result?['status'] as String? ?? '';

    if (mounted && taskId != null) {
      _msgStatus[msgId] = '📥 服务器已收到';
      setState(() {});

      // 轮询状态直到完成
      String? lastStatus;
      for (int i = 0; i < 300; i++) {
        await Future.delayed(const Duration(seconds: 1));
        try {
          final st = await api.getTaskStatus(taskId);
          if (st == null) continue;
          final s = st['status'] as String? ?? '';
          final d = st['detail'] as String? ?? '';
          if (s != lastStatus) {
            lastStatus = s;
            _msgStatus[msgId] = _statusLabel(s, d);
            // 同步更新顶部状态
            if (s == 'agent_received') _headerStatus = '📩 小青已收到';
            if (s == 'agent_replying') _headerStatus = '💬 正在回复...';
            if (mounted) setState(() {});
          }
          if (s == 'completed') {
            final reply = st['reply'] as String? ?? '';
            if (reply.isNotEmpty && mounted) {
              setState(() {
                _sending = false;
                _headerStatus = '🟢 在线';
                _msgStatus.remove(msgId);
                _messages.add(Message(
                  id: DateTime.now().microsecondsSinceEpoch.toString(),
                  content: reply,
                  fromAgent: widget.agentId,
                  toAgent: 'user',
                  isMe: false,
                ));
              });
              _scrollToBottom();
            }
            return;
          }
          if (s == 'failed') {
            if (mounted) {
              setState(() {
                _sending = false;
                _headerStatus = '🟢 在线';
              });
            }
            return;
          }
        } catch (_) {}
      }
      _msgStatus[msgId] = '⏱️ 处理超时';
      if (mounted) setState(() { _sending = false; _headerStatus = '🟢 在线'; });
    } else if (mounted) {
      _msgStatus[msgId] = '⚠️ 发送失败';
      setState(() => _sending = false);
    }
  }

  /// 长按消息弹出操作菜单
  void _showMessageActions(Message msg) {
    final isUser = msg.isMe || msg.fromAgent == 'user';
    final text = msg.content;
    showModalBottomSheet(
      context: context,
      backgroundColor: Theme.of(context).cardColor,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
      ),
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(width: 40, height: 4,
                decoration: BoxDecoration(color: Colors.grey[300], borderRadius: BorderRadius.circular(2)),
              ),
              const SizedBox(height: 8),
              // 引用
              ListTile(
                leading: const Icon(Icons.format_quote, color: Color(0xFF07C160)),
                title: const Text('引用'),
                onTap: () { Navigator.pop(context); _quoteMessage(msg); },
              ),
              // 复制
              ListTile(
                leading: const Icon(Icons.copy, color: Color(0xFF3498db)),
                title: const Text('复制'),
                onTap: () {
                  Navigator.pop(context);
                  Clipboard.setData(ClipboardData(text: text));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('已复制'), duration: Duration(seconds: 1)),
                  );
                },
              ),
              // 转发
              ListTile(
                leading: const Icon(Icons.share, color: Color(0xFFe67e22)),
                title: const Text('转发'),
                onTap: () { Navigator.pop(context); _forwardMessage(msg); },
              ),
              // 收藏
              ListTile(
                leading: const Icon(Icons.star_border, color: Color(0xFFf1c40f)),
                title: const Text('收藏'),
                onTap: () { Navigator.pop(context); _favoriteMessage(msg); },
              ),
              // 多选
              ListTile(
                leading: const Icon(Icons.checklist, color: Color(0xFF9b59b6)),
                title: const Text('多选'),
                onTap: () { Navigator.pop(context); _enterMultiSelect(msg); },
              ),
              // 删除（自己的消息可删）
              if (isUser)
                ListTile(
                  leading: const Icon(Icons.delete_outline, color: Colors.red),
                  title: Text('删除', style: TextStyle(color: Colors.red[400])),
                  onTap: () { Navigator.pop(context); _deleteMessage(msg); },
                ),
            ],
          ),
        ),
      ),
    );
  }

  // ── 操作回调（暂为占位，后续可实现具体逻辑）──
  void _quoteMessage(Message msg) {
    _textCtrl.text = '[引用] ${msg.content}\n';
    _textCtrl.selection = TextSelection.fromPosition(
      TextPosition(offset: _textCtrl.text.length),
    );
    _focusNode.requestFocus();
  }

  void _forwardMessage(Message msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('转发功能开发中'), duration: Duration(seconds: 1)),
    );
  }

  void _favoriteMessage(Message msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('已收藏'), duration: Duration(seconds: 1)),
    );
  }

  void _enterMultiSelect(Message msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('多选功能开发中'), duration: Duration(seconds: 1)),
    );
  }

  void _deleteMessage(Message msg) {
    setState(() => _messages.removeWhere((m) => m.id == msg.id));
  }

  /// 智能体状态中文映射（单参数）  
  String _agentStatusLabel(String status) {
    switch (status) {
      case 'online': return '🟢 在线';
      case 'thinking': return '💭 思考中';
      case 'working': return '⚙️ 工作中';
      case 'idle': return '💤 空闲';
      case 'offline': return '🔴 离线';
      default: return status;
    }
  }

  /// 消息任务状态中文映射（含详情）
  String _statusLabel(String status, String detail) {
    switch (status) {
      case 'received': return '📥 服务器已收到';
      case 'processing': return '⚙️ 处理中';
      case 'forwarding': return '🔄 $detail';
      case 'agent_received': return '📩 $detail';
      case 'agent_replying': return '💬 $detail';
      case 'completed': return '✅ 已完成';
      case 'failed': return '❌ $detail';
      default: return detail.isEmpty ? status : detail;
    }
  }

  // ========== 文件/图片上传 ==========

  final ImagePicker _imagePicker = ImagePicker();

  Future<void> _showFilePickerOptions() async {
    final ctx = context;
    await showModalBottomSheet(
      context: ctx,
      backgroundColor: Theme.of(context).cardColor,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
      ),
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 8),
              Container(
                width: 40, height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),
              ListTile(
                leading: const Icon(Icons.photo_library, color: Color(0xFF07C160)),
                title: const Text('从相册选择'),
                onTap: () {
                  Navigator.pop(ctx);
                  _pickAndSendImage(ImageSource.gallery);
                },
              ),
              ListTile(
                leading: const Icon(Icons.camera_alt, color: Color(0xFF3498db)),
                title: const Text('拍照'),
                onTap: () {
                  Navigator.pop(ctx);
                  _pickAndSendImage(ImageSource.camera);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _pickAndSendImage(ImageSource source) async {
    try {
      final XFile? image = await _imagePicker.pickImage(
        source: source,
        maxWidth: 1920,
        maxHeight: 1920,
      );
      if (image == null) return;

      final bytes = await image.readAsBytes();
      if (bytes.isEmpty) return;

      final name = image.name;

      setState(() {
        _messages.add(Message(
          id: DateTime.now().microsecondsSinceEpoch.toString(),
          content: '📤 上传中: $name',
          fromAgent: 'user',
          toAgent: widget.agentId,
          isMe: true,
        ));
      });
      _scrollToBottom();

      final uploadResult = await api.uploadFile(bytes, name);
      if (uploadResult == null) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('文件上传失败'), duration: Duration(seconds: 2)),
          );
        }
        return;
      }

      // 构造 FILE 消息
      final ext = name.contains('.') ? name.split('.').last : '';
      final fileMsg = '[FILE]' + json.encode({
        'name': uploadResult['name'],
        'size': uploadResult['size'],
        'type': 'image/$ext',
        'url': uploadResult['url'],
      });

      final result = await api.sendMessage(fileMsg, widget.sessionId, widget.agentId);
      final taskId = result?['task_id'] as String?;
      final reply = taskId != null ? await api.pollMessageReply(taskId) : null;

      if (mounted) {
        setState(() {
          _messages.removeLast();
          _messages.add(Message(
            id: DateTime.now().microsecondsSinceEpoch.toString(),
            content: fileMsg,
            fromAgent: 'user',
            toAgent: widget.agentId,
            isMe: true,
          ));
          if (reply != null) {
            _messages.add(Message(
              id: DateTime.now().microsecondsSinceEpoch.toString(),
              content: reply,
              fromAgent: widget.agentId,
              toAgent: 'user',
              isMe: false,
            ));
          }
        });
        _scrollToBottom();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('选择失败: $e'), duration: Duration(seconds: 2)),
        );
      }
    }
  }

  // ========== 语音输入（点一下录音→绿环→再点一下停→文字填入输入框，手动发） ==========

  void _toggleRecording() {
    if (_isRecording) {
      _stopRecording();
    } else {
      _startRecording();
    }
  }

  Future<void> _startRecording() async {
    // 引擎还没初始化→实时初始化（只点话筒时触发）
    if (!_voiceReady) {
      final ok = await _voice.init();
      if (!mounted) return;
      _voiceReady = ok;
      if (!ok) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('语音引擎初始化失败: ${_voice.lastError ?? "未知错误"}'), duration: const Duration(seconds: 3)),
          );
        }
        return;
      }
    }

    // 只在按下麦克风时才请求权限
    final hasPermission = await Permission.microphone.request().isGranted;
    if (!hasPermission) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('需要麦克风权限'), duration: Duration(seconds: 2)),
        );
      }
      return;
    }

    // 开始录音
    final dir = await getTemporaryDirectory();
    _recordPath = '${dir.path}/voice_${DateTime.now().millisecondsSinceEpoch}.wav';

    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.wav,
        sampleRate: 16000,
        numChannels: 1,
      ),
      path: _recordPath!,
    );

    setState(() => _isRecording = true);
  }

  Future<void> _stopRecording() async {
    if (!_isRecording) return;

    setState(() => _isRecording = false);

    final path = _recordPath;
    _recordPath = null;

    try {
      await _recorder.stop();
    } catch (_) {}

    if (path == null || !File(path).existsSync()) return;

    // sherpa-onnx 转文字
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('识别中...'), duration: Duration(seconds: 10)),
    );

    final text = await _voice.transcribe(path);

    // 清理录音文件
    try { File(path).delete(); } catch (_) {}

    if (text != null && text.isNotEmpty) {
      // ✅ 填入输入框，不自动发送
      _textCtrl.text = text;
      _textCtrl.selection = TextSelection.fromPosition(
        TextPosition(offset: text.length),
      );
      _focusNode.requestFocus();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('未识别到文字，请重试'), duration: Duration(seconds: 2)),
        );
      }
    }
  }

  // ========== 构建 ==========

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        titleSpacing: 0,
        title: Row(
          children: [
            CircleAvatar(
              backgroundColor: widget.agentColor,
              radius: 16,
              child: Text(
                widget.agentAvatar,
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14),
              ),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(widget.agentName, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                Text(
                  _agentStatusLabel(_headerStatus),
                  style: TextStyle(fontSize: 11, color: Colors.grey[500]),
                ),
              ],
            ),
          ],
        ),
        centerTitle: false,
        backgroundColor: Theme.of(context).scaffoldBackgroundColor,
        surfaceTintColor: Colors.transparent,
        elevation: 0.5,
        shadowColor: Colors.black12,
      ),
      body: Column(
        children: [
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            CircleAvatar(
                              backgroundColor: widget.agentColor.withOpacity(0.15),
                              radius: 32,
                              child: Text(
                                widget.agentAvatar,
                                style: TextStyle(color: widget.agentColor, fontWeight: FontWeight.w700, fontSize: 24),
                              ),
                            ),
                            const SizedBox(height: 12),
                            Text(
                              '开始和 ${widget.agentName} 对话吧',
                              style: TextStyle(color: Colors.grey[400], fontSize: 14),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollCtrl,
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        itemCount: _messages.length,
                        itemBuilder: (_, i) => _buildMessageBubble(_messages[i]),
                      ),
          ),
          _buildInputBar(),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(Message msg) {
    // ── 系统消息 ──
    if (msg.fromAgent == 'system') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Center(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.grey[200],
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              msg.content,
              style: TextStyle(color: Colors.grey[600], fontSize: 12),
            ),
          ),
        ),
      );
    }

    // ── 文件消息 ──
    if (msg.hasFile) {
      return _buildFileBubble(msg);
    }

    // ── 普通文本消息 ──
    final isUser = msg.isMe || msg.fromAgent == 'user';
    final statusText = _msgStatus[msg.id];

    // 时间戳格式化
    String timeStr = '';
    try {
      final now = DateTime.now();
      final dt = msg.timestamp;
      if (dt.year == now.year && dt.month == now.month && dt.day == now.day) {
        timeStr = '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
      } else {
        timeStr = '${dt.month}/${dt.day} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
      }
    } catch (_) {}

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Column(
        crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
          if (!isUser) ..._buildAgentAvatar(),
          if (!isUser)
            GestureDetector(
              onLongPress: () => _showMessageActions(msg),
              child: Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.68),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(msg.content, style: const TextStyle(color: Color(0xFF191919), fontSize: 15, height: 1.4)),
                ),
                Positioned(left: -6, top: 12,
                  child: CustomPaint(size: const Size(6, 10), painter: TrianglePainter(isLeft: true, color: Colors.white)),
                ),
              ],
            )
            )
          else
            GestureDetector(
              onLongPress: () => _showMessageActions(msg),
              child: Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.68),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF95EC69),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(msg.content, style: const TextStyle(color: Color(0xFF191919), fontSize: 15, height: 1.4)),
                ),
                Positioned(right: -6, top: 12,
                  child: CustomPaint(size: const Size(6, 10), painter: TrianglePainter(isLeft: false, color: const Color(0xFF95EC69))),
                ),
              ],
            ),
            ),
          if (isUser) const SizedBox(width: 8),
        ],
      ),
      if (timeStr.isNotEmpty)
        Padding(
          padding: EdgeInsets.only(top: 1, right: isUser ? 4 : 44),
          child: Text(timeStr, style: TextStyle(color: Colors.grey[400], fontSize: 10)),
        ),
      if (statusText != null)
        Padding(
          padding: EdgeInsets.only(top: 2, right: isUser ? 4 : 0, left: isUser ? 0 : 44),
          child: Text(statusText, style: TextStyle(color: Colors.grey[400], fontSize: 10)),
        ),
    ],
      ),
    );
  }

  // ── 文件/图片气泡 ──
  Widget _buildFileBubble(Message msg) {
    final meta = msg.parsedFileMeta;
    final isUser = msg.isMe || msg.fromAgent == 'user';

    Widget fileWidget;
    if (meta != null && meta.isImage) {
      // 图片 — 显示缩略图
      final imgUrl = '${api.baseUrl}${meta.url}';
      fileWidget = ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Image.network(
          imgUrl,
          width: 200,
          height: 200,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => const Icon(Icons.broken_image, size: 48, color: Colors.grey),
          loadingBuilder: (_, child, progress) {
            if (progress == null) return child;
            return Container(
              width: 200, height: 200,
              color: Colors.grey[200],
              child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
            );
          },
        ),
      );
    } else {
      // 普通文件 — 图标 + 文件名 + 大小
      fileWidget = Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.6),
        padding: const EdgeInsets.all(10),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.insert_drive_file_outlined, size: 32, color: Color(0xFF576B95)),
            const SizedBox(width: 8),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    meta?.name ?? '文件',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF191919)),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (meta != null)
                    Text(meta.sizeStr, style: TextStyle(fontSize: 11, color: Colors.grey[500])),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ..._buildAgentAvatar(),
          if (!isUser)
            Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.72),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: fileWidget,
                ),
                Positioned(left: -6, top: 12,
                  child: CustomPaint(size: const Size(6, 10), painter: TrianglePainter(isLeft: true, color: Colors.white)),
                ),
              ],
            )
          else
            Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.72),
                  decoration: BoxDecoration(
                    color: const Color(0xFF95EC69),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: fileWidget,
                ),
                Positioned(right: -6, top: 12,
                  child: CustomPaint(size: const Size(6, 10), painter: TrianglePainter(isLeft: false, color: const Color(0xFF95EC69))),
                ),
              ],
            ),
          if (isUser) const SizedBox(width: 8),
        ],
      ),
    );
  }

  List<Widget> _buildAgentAvatar() {
    return [
      Padding(
        padding: const EdgeInsets.only(top: 4),
        child: CircleAvatar(
          backgroundColor: widget.agentColor,
          radius: 18,
          child: Text(
            widget.agentAvatar,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14),
          ),
        ),
      ),
      const SizedBox(width: 8),
    ];
  }

  // ========== 输入栏 ==========

  Widget _buildInputBar() {
    return Container(
      padding: EdgeInsets.only(
        left: 4, right: 8, top: 6,
        bottom: MediaQuery.of(context).padding.bottom + 6,
      ),
      decoration: const BoxDecoration(
        color: Color(0xFFF7F7F7),
        border: Border(top: BorderSide(color: Color(0xFFD9D9D9), width: 0.5)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          // 📎 文件按钮
          IconButton(
            icon: const Icon(Icons.add_circle_outline, color: Color(0xFF8E8E93), size: 26),
            onPressed: _showFilePickerOptions,
            padding: const EdgeInsets.only(bottom: 4),
            constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
          ),
          // 文本输入
          Expanded(
            child: Container(
              constraints: const BoxConstraints(maxHeight: 100),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: const Color(0xFFD9D9D9), width: 0.5),
              ),
              child: TextField(
                controller: _textCtrl,
                focusNode: _focusNode,
                maxLines: null,
                minLines: 1,
                style: const TextStyle(fontSize: 16, color: Color(0xFF191919)),
                decoration: const InputDecoration(
                  hintText: '输入消息...',
                  hintStyle: TextStyle(color: Color(0xFFB0B0B0)),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  isCollapsed: true,
                ),
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _sendMessage(),
              ),
            ),
          ),
          const SizedBox(width: 2),
          // 🎤 语音（点一下录音→绿环→再点一下停→文字填入输入框）
          if (_textCtrl.text.isEmpty || _isRecording)
            GestureDetector(
              onTap: _toggleRecording,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                width: 36, height: 36,
                margin: const EdgeInsets.only(bottom: 2),
                decoration: BoxDecoration(
                  color: _isRecording ? const Color(0xFF07C160).withOpacity(0.15) : Colors.transparent,
                  shape: BoxShape.circle,
                  border: _isRecording
                      ? Border.all(color: const Color(0xFF07C160), width: 2)
                      : null,
                  boxShadow: _isRecording
                      ? [BoxShadow(
                          color: const Color(0xFF07C160).withOpacity(0.3),
                          blurRadius: 8,
                          spreadRadius: 1,
                        )]
                      : null,
                ),
                child: Icon(
                  _isRecording ? Icons.mic : Icons.mic_none,
                  color: _isRecording ? const Color(0xFF07C160) : const Color(0xFF8E8E93),
                  size: 26,
                ),
              ),
            )
          else
            GestureDetector(
              onTap: _textCtrl.text.isNotEmpty ? () => _sendMessage() : null,
              child: Container(
                width: 36, height: 36,
                margin: const EdgeInsets.only(bottom: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFF07C160),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Icon(Icons.arrow_upward, color: Colors.white, size: 20),
              ),
            ),
        ],
      ),
    );
  }
}

/// 气泡三角绘制
class TrianglePainter extends CustomPainter {
  final bool isLeft;
  final Color color;

  TrianglePainter({required this.isLeft, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color;
    final path = Path();
    if (isLeft) {
      path.moveTo(0, 4);
      path.lineTo(6, 0);
      path.lineTo(6, 12);
      path.close();
    } else {
      path.moveTo(6, 4);
      path.lineTo(0, 0);
      path.lineTo(0, 12);
      path.close();
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
