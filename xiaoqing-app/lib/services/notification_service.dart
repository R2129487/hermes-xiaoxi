import 'dart:async';
import 'dart:io';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';

/// 通知服务 — 新消息时弹通知 + App图标红点
class NotificationService {
  static final NotificationService _instance = NotificationService._();
  factory NotificationService() => _instance;
  NotificationService._();

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _initialized = false;
  int _unreadCount = 0;

  /// 初始化通知
  Future<void> init() async {
    if (_initialized) return;

    // Android 13+ 需要运行时申请通知权限
    if (Platform.isAndroid) {
      final status = await Permission.notification.request();
      print('[NotificationService] 📋 通知权限: $status');
    }

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidSettings);

    await _plugin.initialize(initSettings);

    // 创建通知渠道（Android 8+）
    await _createNotificationChannel();

    _initialized = true;
    print('[NotificationService] ✅ 通知初始化完成');
  }

  /// 创建Android通知渠道
  Future<void> _createNotificationChannel() async {
    const channel = AndroidNotificationChannel(
      'xiaoxi_messages',
      '新消息通知',
      description: '收到智能体新消息时通知',
      importance: Importance.high,
      enableVibration: true,
      playSound: true,
    );

    await _plugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);
    print('[NotificationService] 📢 通知渠道已创建');
  }

  /// 显示新消息通知
  Future<void> showMessageNotification({
    required String agentName,
    required String content,
    required int chatIndex,
  }) async {
    if (!_initialized) await init();

    _unreadCount++;
    print('[NotificationService] 🔔 弹通知: $agentName → ${content.substring(0, content.length.clamp(0, 50))}');

    final androidDetails = AndroidNotificationDetails(
      'xiaoxi_messages',
      '新消息通知',
      channelDescription: '收到智能体新消息时通知',
      importance: Importance.high,
      priority: Priority.high,
      icon: '@mipmap/ic_launcher',
      styleInformation: BigTextStyleInformation(content),
    );

    final details = NotificationDetails(android: androidDetails);

    await _plugin.show(
      chatIndex, // 用chatIndex作为id，同一聊天的通知会覆盖
      agentName,
      content.length > 100 ? '${content.substring(0, 100)}...' : content,
      details,
    );
    print('[NotificationService] ✅ 通知已发送');
  }

  /// 清除未读计数
  void clearUnread() {
    _unreadCount = 0;
  }

  /// 获取未读数
  int get unreadCount => _unreadCount;
}
