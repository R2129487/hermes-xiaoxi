import 'dart:convert';

/// 文件元数据
class FileMeta {
  final String name;
  final int size;
  final String type;
  final String url;

  FileMeta({required this.name, required this.size, required this.type, required this.url});

  factory FileMeta.fromJson(Map<String, dynamic> json) => FileMeta(
    name: json['name'] ?? '',
    size: json['size'] ?? 0,
    type: json['type'] ?? '',
    url: json['url'] ?? '',
  );

  String get sizeStr {
    if (size > 1024 * 1024) return '${(size / 1024 / 1024).toStringAsFixed(1)}MB';
    return '${(size / 1024).toStringAsFixed(1)}KB';
  }

  bool get isImage => type.startsWith('image/');
}

/// 消息模型
class Message {
  final String id;
  final String content;
  final String fromAgent;
  final String toAgent;
  final DateTime timestamp;
  final bool isMe;
  final FileMeta? fileMeta;

  Message({
    required this.id,
    required this.content,
    this.fromAgent = 'user',
    this.toAgent = '',
    DateTime? timestamp,
    this.isMe = false,
    this.fileMeta,
  }) : timestamp = timestamp ?? DateTime.now();

  bool get hasFile => content.startsWith('[FILE]');

  FileMeta? get parsedFileMeta {
    if (!hasFile) return null;
    try {
      final jsonStr = content.substring(6);
      return FileMeta.fromJson(json.decode(jsonStr));
    } catch (_) {
      return null;
    }
  }
}
