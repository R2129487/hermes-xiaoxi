import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import '../models/message.dart';

/// 本地消息缓存 — SQLite持久化，切换页面秒开
class MessageCache {
  static Database? _db;

  static Future<Database> get database async {
    if (_db != null) return _db!;
    final dbPath = await getDatabasesPath();
    _db = await openDatabase(
      join(dbPath, 'messages.db'),
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE messages (
            session_id TEXT NOT NULL,
            msg_id TEXT NOT NULL,
            content TEXT NOT NULL,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_me INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (session_id, msg_id)
          )
        ''');
        await db.execute('CREATE INDEX idx_session ON messages(session_id, timestamp)');
      },
    );
    return _db!;
  }

  /// 获取某会话的全部消息（按时间排序）
  static Future<List<Message>> getMessages(String sessionId) async {
    final db = await database;
    final rows = await db.query(
      'messages',
      where: 'session_id = ?',
      whereArgs: [sessionId],
      orderBy: 'timestamp ASC',
    );
    return rows.map((r) => Message(
      id: r['msg_id'] as String,
      content: r['content'] as String,
      fromAgent: r['from_agent'] as String,
      toAgent: r['to_agent'] as String,
      timestamp: DateTime.tryParse(r['timestamp'] as String) ?? DateTime.now(),
      isMe: (r['is_me'] as int) == 1,
    )).toList();
  }

  /// 获取某会话最后一条消息（用于聊天列表预览）
  static Future<Message?> getLastMessage(String sessionId) async {
    final db = await database;
    final rows = await db.query(
      'messages',
      where: 'session_id = ?',
      whereArgs: [sessionId],
      orderBy: 'timestamp DESC',
      limit: 1,
    );
    if (rows.isEmpty) return null;
    final r = rows.first;
    return Message(
      id: r['msg_id'] as String,
      content: r['content'] as String,
      fromAgent: r['from_agent'] as String,
      toAgent: r['to_agent'] as String,
      timestamp: DateTime.tryParse(r['timestamp'] as String) ?? DateTime.now(),
      isMe: (r['is_me'] as int) == 1,
    );
  }

  /// 批量写入消息（网络刷新后调用，增量更新）
  static Future<void> putMessages(String sessionId, List<Message> msgs) async {
    final db = await database;
    await db.transaction((txn) async {
      for (final m in msgs) {
        await txn.insert(
          'messages',
          {
            'session_id': sessionId,
            'msg_id': m.id,
            'content': m.content,
            'from_agent': m.fromAgent,
            'to_agent': m.toAgent,
            'timestamp': m.timestamp.toIso8601String(),
            'is_me': m.isMe ? 1 : 0,
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }
    });
  }

  /// 清除某会话缓存
  static Future<void> clearSession(String sessionId) async {
    final db = await database;
    await db.delete('messages', where: 'session_id = ?', whereArgs: [sessionId]);
  }
}
