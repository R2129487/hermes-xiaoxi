import 'dart:async';
import 'dart:io';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';

/// 通知服务 — 新消息时弹通知 + App图标红点 + 点击跳转 + 处理状态通知
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

    // 创建通知渠道
    await _createNotificationChannels();
    _initialized = true;
    print('[NotificationService] ✅ 通知初始化完成');
  }

  /// 创建Android通知渠道
  Future<void> _createNotificationChannels() async {
    final androidPlugin = _plugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();

    // 渠道1: 新消息通知（点击后消失）
    await androidPlugin?.createNotificationChannel(const AndroidNotificationChannel(
      'xiaoxi_messages',
      '新消息通知',
      description: '收到智能体新消息时通知',
      importance: Importance.high,
      enableVibration: true,
      playSound: true,
    ));

    // 渠道2: 处理状态通知（常驻，不自动消失）
    await androidPlugin?.createNotificationChannel(const AndroidNotificationChannel(
      'xiaoxi_processing',
      '处理状态',
      description: '智能体处理任务时的实时状态',
      importance: Importance.high,
      enableVibration: false,
      playSound: false,
    ));

    print('[NotificationService] 📢 通知渠道已创建');
  }

  /// 根据agent_id生成唯一通知ID
  int _agentNotificationId(String agentId) {
    return 0x10000 + (agentId.hashCode & 0xFFFF);
  }

  /// 显示处理中状态通知（常驻，不自动消失）
  Future<void> showProcessingNotification({
    required String agentId,
    required String agentName,
    required String detail,
    String? payload,
  }) async {
    if (!_initialized) await init();

    final notificationId = _agentNotificationId(agentId);
    print('[NotificationService] 🔄 处理中通知: $agentName - $detail');

    final androidDetails = AndroidNotificationDetails(
      'xiaoxi_processing',
      '处理状态',
      channelDescription: '智能体处理任务时的实时状态',
      importance: Importance.high,
      priority: Priority.high,
      icon: '@drawable/ic_notification',
      // 常驻通知，不能滑掉
      ongoing: true,
      // 不自动消失
      autoCancel: false,
      // 显示计时器
      showProgress: true,
      maxProgress: 100,
      progress: 50,
      styleInformation: BigTextStyleInformation(
        '$agentName $detail',
        contentTitle: '青 · $agentName',
        summaryText: detail,
      ),
    );

    await _plugin.show(
      notificationId,
      '青 · $agentName',
      detail,
      NotificationDetails(android: androidDetails),
      payload: payload ?? '',
    );
  }

  /// 更新处理中通知的状态
  Future<void> updateProcessingNotification({
    required String agentId,
    required String agentName,
    required String detail,
    int progress = 50,
    String? payload,
  }) async {
    if (!_initialized) return;

    final notificationId = _agentNotificationId(agentId);

    final androidDetails = AndroidNotificationDetails(
      'xiaoxi_processing',
      '处理状态',
      channelDescription: '智能体处理任务时的实时状态',
      importance: Importance.high,
      priority: Priority.high,
      icon: '@drawable/ic_notification',
      ongoing: true,
      autoCancel: false,
      showProgress: true,
      maxProgress: 100,
      progress: progress,
      styleInformation: BigTextStyleInformation(
        '$agentName $detail',
        contentTitle: '青 · $agentName',
        summaryText: detail,
      ),
    );

    await _plugin.show(
      notificationId,
      '青 · $agentName',
      detail,
      NotificationDetails(android: androidDetails),
      payload: payload ?? '',
    );
  }

  /// 取消处理中通知（收到回复后调用）
  Future<void> cancelProcessingNotification(String agentId) async {
    final notificationId = _agentNotificationId(agentId);
    await _plugin.cancel(notificationId);
    print('[NotificationService] ✅ 处理中通知已取消: $agentId');
  }

  /// 显示新消息通知
  Future<void> showMessageNotification({
    required String agentName,
    required String content,
    required int chatIndex,
    String? payload,
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
      autoCancel: true,
      ongoing: false,
    );

    final details = NotificationDetails(android: androidDetails);

    await _plugin.show(
      chatIndex,
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
