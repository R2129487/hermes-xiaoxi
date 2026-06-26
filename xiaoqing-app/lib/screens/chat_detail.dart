import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:permission_handler/permission_handler.dart';
import '../services/dispatcher_api.dart';
import '../models/message.dart';

/// 聊天详情页 — 微信风格消息气泡 + 输入框
class ChatDetail extends StatefulWidget {
  final String agentId;
  final String agentName;
  final Color agentColor;
  final String agentAvatar;
  final String sessionId;

  const ChatDetail({
    super.key,
    required this.agentId,
    required this.agentName,
    required this.agentColor,
    required this.agentAvatar,
    required this.sessionId,
  });

  @override
  State<ChatDetail> createState() => _ChatDetailState();
}

class _ChatDetailState extends State<ChatDetail> {
  final DispatcherApi _api = DispatcherApi();
  final TextEditingController _textCtrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();
  final FocusNode _focusNode = FocusNode();
  List<Message> _messages = [];
  bool _loading = true;
  bool _sending = false;

  // 语音识别
  late stt.SpeechToText _speech;
  bool _isListening = false;
  String _lastWords = '';

  @override
  void initState() {
    super.initState();
    _speech = stt.SpeechToText();
    _loadHistory();
    _textCtrl.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _textCtrl.dispose();
    _scrollCtrl.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  Future<void> _loadHistory() async {
    final msgs = await _api.getHistory(widget.sessionId);
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

  Future<void> _sendMessage({String? text}) async {
    final msg = text ?? _textCtrl.text.trim();
    if (msg.isEmpty || _sending) return;

    _textCtrl.clear();
    setState(() {
      _sending = true;
      _messages.add(Message(
        id: DateTime.now().microsecondsSinceEpoch.toString(),
        content: msg,
        fromAgent: 'user',
        toAgent: widget.agentId,
        isMe: true,
      ));
    });
    _scrollToBottom();

    final reply = await _api.sendMessage(msg, widget.sessionId, widget.agentId);

    if (mounted) {
      setState(() {
        _sending = false;
        if (reply != null) {
          _messages.add(Message(
            id: DateTime.now().microsecondsSinceEpoch.toString(),
            content: reply,
            fromAgent: widget.agentId,
            toAgent: 'user',
            isMe: false,
          ));
        } else {
          _messages.add(Message(
            id: DateTime.now().microsecondsSinceEpoch.toString(),
            content: '⚠️ 发送失败，请重试',
            fromAgent: 'system',
            toAgent: 'user',
            isMe: false,
          ));
        }
      });
      _scrollToBottom();
    }
  }

  // ========== 文件/图片上传 ==========

  final ImagePicker _imagePicker = ImagePicker();

  Future<void> _showFilePickerOptions() async {
    final ctx = context;
    await showModalBottomSheet(
      context: ctx,
      backgroundColor: Colors.white,
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

      final uploadResult = await _api.uploadFile(bytes, name);
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

      final reply = await _api.sendMessage(fileMsg, widget.sessionId, widget.agentId);

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

  // ========== 语音输入 ==========

  Future<void> _startListening() async {
    final hasPermission = await Permission.microphone.request().isGranted;
    if (!hasPermission) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('需要麦克风权限'), duration: Duration(seconds: 2)),
        );
      }
      return;
    }

    final available = await _speech.initialize();
    if (!available) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('语音识别不可用'), duration: Duration(seconds: 2)),
        );
      }
      return;
    }

    setState(() => _isListening = true);
    _speech.listen(
      onResult: (result) {
        setState(() {
          _lastWords = result.recognizedWords;
          _textCtrl.text = _lastWords;
          // 光标移到末尾
          _textCtrl.selection = TextSelection.fromPosition(
            TextPosition(offset: _textCtrl.text.length),
          );
        });
      },
      localeId: 'zh_CN',
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
      partialResults: true,
    );
  }

  void _stopListening() {
    _speech.stop();
    setState(() => _isListening = false);
    // 有文字直接发送
    if (_textCtrl.text.trim().isNotEmpty) {
      _sendMessage();
    }
  }

  // ========== 构建 ==========

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFEDEDED),
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              backgroundColor: widget.agentColor,
              radius: 16,
              child: Text(
                widget.agentAvatar,
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14),
              ),
            ),
            const SizedBox(width: 8),
            Text(widget.agentName, style: const TextStyle(fontSize: 17)),
          ],
        ),
        centerTitle: true,
        backgroundColor: const Color(0xFFEDEDED),
        surfaceTintColor: Colors.transparent,
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
          else
            Stack(
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
          if (isUser) const SizedBox(width: 8),
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
      final imgUrl = '${_api.baseUrl}${meta.url}';
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
          // 🎤 语音 或 ➤ 发送
          if (_textCtrl.text.isEmpty && !_isListening)
            IconButton(
              icon: Icon(
                _isListening ? Icons.mic : Icons.mic_none,
                color: _isListening ? Colors.red : const Color(0xFF8E8E93),
                size: 26,
              ),
              onPressed: _startListening,
              padding: const EdgeInsets.only(bottom: 4),
              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
            )
          else if (_isListening)
            GestureDetector(
              onTap: _stopListening,
              child: Container(
                width: 36, height: 36,
                margin: const EdgeInsets.only(bottom: 2),
                decoration: BoxDecoration(
                  color: Colors.red,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Icon(Icons.stop, color: Colors.white, size: 20),
              ),
            )
          else
            GestureDetector(
              onTap: _textCtrl.text.isNotEmpty ? () => _sendMessage() : null,
              child: Container(
                width: 36, height: 36,
                margin: const EdgeInsets.only(bottom: 2),
                decoration: BoxDecoration(
                  color: _textCtrl.text.isNotEmpty
                      ? const Color(0xFF07C160)
                      : const Color(0xFFB0B0B0),
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
