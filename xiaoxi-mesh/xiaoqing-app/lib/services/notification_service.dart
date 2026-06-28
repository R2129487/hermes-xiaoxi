import 'dart:async';
import 'dart:io';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';

/// 通知服务 — 新消息时弹通知 + App图标红点 + 点击跳转
class NotificationService {
  static final NotificationService _instance = NotificationService._();
  factory NotificationService() => _instance;
  NotificationService._();

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _initialized = false;
  int _unreadCount = 0;

  /// 通知点击回调（用于跳转到对应聊天）
  Function(String payload)? onNotificationTap;

  /// 初始化通知
  Future<void> init() async {
    if (_initialized) return;

    // Android 13+ 需要运行时申请通知权限
    if (Platform.isAndroid) {
      final status = await Permission.notification.request();
      print('[NotificationService] 📋 通知权限: $status');
    }

    const androidSettings = AndroidInitializationSettings('@drawable/ic_notification');
    const initSettings = InitializationSettings(android: androidSettings);

    await _plugin.initialize(
      initSettings,
      onDidReceiveNotificationResponse: (details) {
        print('[NotificationService] 🔔 通知被点击: payload=${details.payload}');
        if (details.payload != null && details.payload!.isNotEmpty) {
          onNotificationTap?.call(details.payload!);
        }
      },
    );

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
    String? payload,  // 点击通知后跳转的参数
  }) async {
    if (!_initialized) await init();

    _unreadCount++;
    final displayContent = content.length > 100 ? '${content.substring(0, 100)}...' : content;
    print('[NotificationService] 🔔 弹通知: $agentName → $displayContent');

    final androidDetails = AndroidNotificationDetails(
      'xiaoxi_messages',
      '新消息通知',
      channelDescription: '收到智能体新消息时通知',
      importance: Importance.high,
      priority: Priority.high,
      icon: '@drawable/ic_notification',
      largeIcon: const DrawableResourceAndroidBitmap('@mipmap/ic_launcher'),
      styleInformation: BigTextStyleInformation(displayContent),
      // 通知点击后自动消失
      autoCancel: true,
      // 保留通知在通知栏
      ongoing: false,
    );

    final details = NotificationDetails(android: androidDetails);

    await _plugin.show(
      chatIndex, // 用chatIndex作为id，同一聊天的通知会覆盖
      agentName,
      displayContent,
      details,
      payload: payload ?? '',
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
