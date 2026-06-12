# 小希固件 · 全模块架构设计 v1.0

> 架构一次搭全，模块逐个填充
> ESP32 是身体，Agent 后端是大脑

---

## 模块总览

```
┌─────────────────────────────────────────────────────────────┐
│                    小希固件 · 模块架构                         │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                    核心层 (Core)                        │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │    │
│  │  │ 应用调度   │  │ 状态机    │  │ 事件总线  │            │    │
│  │  │ App       │  │ State    │  │ EventBus │            │    │
│  │  └──────────┘  └──────────┘  └──────────┘            │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐│
│  │ 🎤 听觉  │  │ 👁️ 视觉  │  │ 🦵 运动  │  │ 🔈 输出  │  │ 📡 通信 ││
│  │ Audio   │  │ Vision │  │ Motion │  │ Output │  │ Comm   ││
│  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘│
│      │           │           │           │           │       │
│  ┌───┴───────────┴───────────┴───────────┴───────────┴───┐  │
│  │                    硬件抽象层 (HAL)                      │  │
│  │  Board · Codec · I2S · GPIO · SPI · I2C · UART · WiFi │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 模块详细设计

### 模块 1：🎤 听觉 (Audio)

**职责：** 录音、唤醒词检测、语音活动检测(VAD)、音频预处理

```
audio/
├── audio_codec.h/cc          # I2S 音频编解码抽象（搬自小智）
├── audio_pipeline.h/cc       # 🆕 音频管线编排
│   ├── record()              # 开始录音 → PCM 数据
│   ├── stop()                # 停止录音
│   ├── get_frame()           # 获取一帧音频
│   └── is_voice_active()     # VAD 判断
├── codecs/                   # Codec 驱动（搬自小智）
│   ├── es8311.h/cc
│   ├── es8388.h/cc
│   ├── es8374.h/cc
│   └── dummy_codec.h/cc      # 测试用
├── wake_word.h/cc            # 唤醒词检测接口
│   ├── esp_wake_word.h/cc    # ESP-SR WakeNet 实现
│   ├── button_wake.h/cc      # 按钮触发实现
│   └── disabled_wake.h/cc    # 禁用唤醒词
└── audio_processor.h/cc      # AFE 音频处理（搬自小智）
    ├── AEC 回声消除
    ├── NS 降噪
    └── VAD 语音活动检测
```

**对外接口：**
```c
// 初始化
audio_init(&config);

// 录音控制
audio_start_recording();          // 开始录音
audio_stop_recording();           // 停止录音，返回录音数据
audio_get_pcm_frame(buf, len);    // 获取一帧 PCM

// 唤醒词
audio_wake_word_init();           // 初始化唤醒词
audio_wake_word_detect();         // 检测唤醒词（非阻塞）

// VAD
audio_is_speaking();              // 是否检测到语音
```

**状态：** 从搬小智代码开始，基本可用

---

### 模块 2：👁️ 视觉 (Vision)

**职责：** 摄像头控制、图像采集、视频流传输

```
vision/
├── camera.h/cc               # 🆕 摄像头抽象接口
│   ├── init()                # 初始化摄像头
│   ├── capture_frame()       # 拍一帧照片 → JPEG
│   ├── start_stream()        # 开始视频流
│   ├── stop_stream()         # 停止视频流
│   └── set_resolution()      # 设置分辨率
├── camera_ov2640.h/cc        # OV2640 驱动（ESP32-CAM）
├── camera_ov5640.h/cc        # OV5640 驱动（可选，更高分辨率）
└── image_encoder.h/cc        # 图像编码
    ├── jpeg_encode()         # JPEG 压缩
    └── resize()              # 缩放
```

**对外接口：**
```c
// 初始化
vision_init(&config);

// 拍照
vision_capture(jpeg_buf, &jpeg_len);     // 拍一张 JPEG

// 视频流
vision_stream_start(callback);           // 开始流，每帧回调
vision_stream_stop();                    // 停止流

// 配置
vision_set_resolution(640, 480);
vision_set_quality(80);                  // JPEG 质量
```

**状态：** 全新编写，参考 ESP-IDF 的 camera 驱动示例

**硬件差异：**
| 板子 | 摄像头 | 状态 |
|------|--------|------|
| ESP32-CAM (S3+OV2640) | OV2640 | 优先支持 |
| S3-BOX3 | 无摄像头 | 跳过此模块 |
| 面包板 S3 | 外接 OV2640 | 可选 |
| C3 笔形版 | 无摄像头 | 跳过此模块 |

---

### 模块 3：🦵 运动 (Motion)

**职责：** 舵机控制、电机控制、运动规划执行

```
motion/
├── actuator.h/cc             # 🆕 执行器抽象接口
│   ├── init()                # 初始化运动系统
│   ├── execute()             # 执行一组动作指令
│   ├── stop_all()            # 紧急停止
│   └── get_status()          # 获取当前状态
├── servo.h/cc                # 🆕 舵机驱动
│   ├── init(channel, pin)    # 初始化舵机
│   ├── set_angle(angle)      # 设置角度 (0-180)
│   ├── set_speed(speed)      # 设置速度
│   └── get_angle()           # 获取当前角度
├── motor.h/cc                # 🆕 直流电机驱动
│   ├── init()                # 初始化电机
│   ├── set_speed(speed)      # 设置速度 (-100~100)
│   ├── forward/backward()    # 前进/后退
│   ├── turn_left/right()     # 左转/右转
│   └── stop()                # 停止
├── servo_driver.h/cc         # PCA9685 I2C 舵机驱动板
│   ├── init(i2c_bus)         # 初始化
│   ├── set_pwm(channel, val) # 设置 PWM
│   └── set_all_pwm(val)      # 全部舵机
├── imu.h/cc                  # 🆕 IMU 姿态传感器
│   ├── init()                # MPU6050 初始化
│   ├── get_accel()           # 加速度
│   ├── get_gyro()            # 陀螺仪
│   └── get姿态()             # 姿态角
└── obstacle.h/cc             # 🆕 避障传感器
    ├── ultrasonic_init()     # 超声波 HC-SR04
    ├── get_distance()        # 获取距离 (cm)
    └── is_obstacle()         # 是否有障碍物
```

**对外接口：**
```c
// 初始化
motion_init(&config);

// 舵机控制
motion_servo_set(id, angle, speed);      // 设置舵机角度
motion_servo_batch(cmds, count);         // 批量控制多个舵机

// 电机控制（底盘移动）
motion_move(direction, speed);           // 移动
motion_turn(angle, speed);               // 转弯
motion_stop();                           // 停止

// 安全
motion_emergency_stop();                 // 紧急停止
motion_get_obstacle_distance();          // 获取障碍物距离

// 执行 Agent 下发的动作序列
motion_execute_sequence(actions, count); // 执行动作序列
```

**动作指令格式（Agent → ESP32）：**
```json
{
  "actions": [
    {"type": "servo", "id": 1, "angle": 90, "speed": 50, "duration_ms": 500},
    {"type": "move", "direction": "forward", "speed": 30, "duration_ms": 1000},
    {"type": "servo", "id": 2, "angle": 45, "speed": 80, "duration_ms": 300},
    {"type": "wait", "duration_ms": 200}
  ]
}
```

**状态：** 全新编写，初期只有接口骨架，后面逐个驱动填充

---

### 模块 4：🔈 输出 (Output)

**职责：** 音频播放、显示、LED 状态指示

```
output/
├── player.h/cc               # 🆕 音频播放器
│   ├── init()                # 初始化解码器
│   ├── play_pcm()            # 播放 PCM 数据
│   ├── play_opus()           # 播放 Opus 编码数据
│   ├── play_stream(callback) # 流式播放（回调填充数据）
│   ├── pause/resume()        # 暂停/恢复
│   └── stop()                # 停止播放
├── display.h/cc              # 显示子系统（搬自小智）
│   ├── lcd_display.h/cc      # LCD 显示
│   ├── oled_display.h/cc     # OLED 显示
│   └── no_display.h/cc       # 无显示版本
├── emotion.h/cc              # 🆕 情感/表情管理
│   ├── set_emotion(type)     # 设置表情 (idle/thinking/happy/sad/error)
│   ├── show_text(text)       # 显示文字
│   └── show_status(status)   # 显示状态
└── led_indicator.h/cc        # LED 状态指示（搬自小智）
    ├── set_state(state)      # 待机/录音/思考/播放/错误
    ├── set_color(r, g, b)    # 设置颜色
    └── set_brightness(val)   # 设置亮度
```

**对外接口：**
```c
// 音频播放
output_play_audio(data, len, format);    // 播放音频
output_play_stream_start(format);        // 开始流式播放
output_play_stream_write(data, len);     // 写入流数据
output_play_stream_stop();               // 停止流式播放
output_is_playing();                     // 是否在播放

// 显示
output_display_text(text);               // 显示文字
output_display_emotion(type);            // 显示表情
output_display_clear();                  // 清屏

// LED
output_led_set_state(LED_STATE_LISTENING);  // LED 状态
```

---

### 模块 5：📡 通信 (Comm)

**职责：** WiFi 管理、HTTP 客户端、Agent API 调用

```
comm/
├── wifi_manager.h/cc         # WiFi 管理（搬自小智）
│   ├── init()                # 初始化
│   ├── connect(ssid, pass)   # 连接 WiFi
│   ├── start_ap()            # 开启 AP 热点
│   ├── auto_connect()        # 自动连接已知 WiFi
│   └── is_connected()        # 是否已连接
├── agent_client.h/cc         # 🆕 Agent API 客户端
│   ├── init(base_url, key)   # 初始化
│   ├── asr(pcm_data, len)   # POST /v1/audio/transcriptions → 文本
│   ├── chat(messages)        # POST /v1/chat/completions → SSE 流式文本
│   ├── tts(text)             # POST /v1/audio/speech → 音频流
│   ├── vision_upload(jpeg)   # POST 图像到 Agent → 场景描述
│   └── motion_command(json)  # POST 动作指令 → 执行结果
├── http_client.h/cc          # HTTP 客户端封装
│   ├── post_json()           # JSON POST
│   ├── post_binary()         # 二进制 POST（音频/图像）
│   ├── get()                 # GET 请求
│   └── sse_stream()          # SSE 流式接收
└── web_server.h/cc           # 🆕 本地 Web 配置服务器
    ├── start()               # 启动 HTTP 服务器
    ├── stop()                # 停止
    └── handlers/             # 请求处理器
        ├── page_config.h     # 配置页面 HTML
        ├── api_config.h      # GET/POST /api/config
        ├── api_wifi.h        # POST /api/wifi
        ├── api_status.h      # GET /api/status
        └── api_test.h        # POST /api/test (测试连接)
```

**Agent API 调用流程：**
```c
// 语音对话完整流程
char *text = agent_asr(pcm_data, pcm_len);      // 1. 语音→文字
agent_chat_stream(text, on_token_callback);      // 2. 文字→流式回复
char *audio = agent_tts(reply_text);             // 3. 回复→语音
output_play_audio(audio, audio_len, FORMAT_OPUS); // 4. 播放

// 视觉理解
char *desc = agent_vision_understand(jpeg_buf, jpeg_len, "桌上有什么？");

// 运动控制
agent_motion_execute("把咖啡推到左边", jpeg_buf, jpeg_len);
```

---

### 核心层 (Core)

```
core/
├── application.h/cc          # 应用主循环
│   ├── init()                # 初始化所有模块
│   ├── run()                 # 主循环（事件驱动）
│   └── shutdown()            # 关闭
├── state_machine.h/cc        # 设备状态机（搬自小智）
│   ├── IDLE                  # 待机
│   ├── LISTENING             # 录音中
│   ├── THINKING              # 等待 Agent 响应
│   ├── SPEAKING              # 播放回复中
│   ├── MOVING                # 执行动作中
│   └── CAPTURING             # 视觉采集中
├── event_bus.h/cc            # 🆕 事件总线
│   ├── on(event, callback)   # 注册事件
│   ├── emit(event, data)     # 发射事件
│   └── off(event)            # 取消注册
├── session.h/cc              # 🆕 对话会话管理
│   ├── start()               # 开始新会话
│   ├── add_message()         # 添加消息
│   ├── get_context()         # 获取上下文（发给 Agent）
│   └── clear()               # 清除会话
└── config.h/cc               # 🆕 全局配置（NVS 封装）
    ├── agent_url             # Agent 后端地址
    ├── agent_api_key         # API Key
    ├── model_name            # 模型名
    ├── wifi_ssid/pass        # WiFi 配置
    ├── volume                # 音量
    ├── wake_word_enabled     # 唤醒词开关
    └── device_name           # 设备名称
```

**事件总线事件列表：**
```c
// 输入事件
EVENT_WAKE_WORD_DETECTED       // 唤醒词检测到
EVENT_BUTTON_PRESSED           // 按钮按下
EVENT_BUTTON_RELEASED          // 按钮释放
EVENT_VAD_SPEECH_START         // 语音开始
EVENT_VAD_SPEECH_END           // 语音结束

// Agent 事件
EVENT_ASR_RESULT               // ASR 识别结果
EVENT_LLM_TOKEN                // LLM 流式 token
EVENT_LLM_DONE                 // LLM 回复完成
EVENT_TTS_AUDIO                // TTS 音频数据到达

// 视觉事件
EVENT_VISION_FRAME             // 摄像头一帧图像
EVENT_VISION_RESULT            // 视觉理解结果

// 运动事件
EVENT_MOTION_DONE              // 动作执行完成
EVENT_OBSTACLE_DETECTED        // 检测到障碍物

// 系统事件
EVENT_WIFI_CONNECTED           // WiFi 已连接
EVENT_WIFI_DISCONNECTED        // WiFi 断开
EVENT_ERROR                    // 错误
```

---

### 硬件抽象层 (HAL)

```
hal/
├── board.h/cc                # Board 单例 + 工厂模式（搬自小智）
├── boards/
│   ├── common/
│   │   ├── wifi_board.h/cc   # WiFi Board 基类（搬）
│   │   ├── button.h/cc       # 按钮（搬）
│   │   ├── backlight.h/cc    # 背光（搬）
│   │   └── camera.h/cc       # 摄像头接口（新增）
│   ├── s3_box3/              # ESP32-S3-BOX3
│   ├── bread_board/          # 面包板 S3 套件
│   ├── esp32_cam/            # ESP32-CAM
│   ├── compact_wifi/         # 紧凑 WiFi 板
│   └── pen_c3/               # 笔形 C3 版（未来）
├── i2c_bus.h/cc              # I2C 总线管理
├── spi_bus.h/cc              # SPI 总线管理
├── gpio.h/cc                 # GPIO 管理
└── pwm.h/cc                  # PWM 管理（舵机用）
```

---

## 模块交互时序

### 场景一：语音对话
```
按钮按下 → [Core] 状态机 → IDLE→LISTENING
  → [Audio] 开始录音
按钮释放 → [Audio] 停止录音 → PCM 数据
  → [Comm] agent_asr(pcm) → 文本
  → [Core] 状态机 → THINKING
  → [Comm] agent_chat_stream(text) → SSE 流式回复
  → [Output] 流式播放 TTS 音频
  → [Core] 状态机 → SPEAKING
播放完毕 → [Core] 状态机 → IDLE
```

### 场景二：视觉理解
```
长按按钮 2秒 → [Core] 状态机 → CAPTURING
  → [Vision] capture_frame() → JPEG
  → [Comm] agent_vision_upload(jpeg, "描述一下") → 场景描述
  → [Core] 状态机 → THINKING
  → [Comm] agent_tts(description) → 音频
  → [Output] 播放
  → [Core] 状态机 → IDLE
```

### 场景三：运动控制
```
语音 "把咖啡推到左边"
  → [Audio] 录音 → [Comm] ASR → "把咖啡推到左边"
  → [Vision] capture_frame() → 当前场景
  → [Comm] agent_motion("把咖啡推到左边", jpeg)
  → Agent 返回动作序列 JSON
  → [Motion] execute_sequence(actions)
  → [Output] 播放 "推好了~"
  → [Core] 状态机 → IDLE
```

### 场景四：多模态交互（听+看+动）
```
语音 "帮我看看桌上有什么，把杯子拿到右边"
  → [Audio] ASR → 意图：需要视觉+运动
  → [Vision] 拍照 → JPEG
  → [Comm] Agent 处理（视觉理解+动作规划）
  → Agent 返回：场景描述 + 动作序列
  → [Motion] 执行动作
  → [Output] 播放回复
```

---

## 文件结构总览

```
xiaoxi-firmware/
├── main/
│   ├── main.cc                    # 入口
│   │
│   ├── core/                      # 核心层
│   │   ├── application.h/cc
│   │   ├── state_machine.h/cc
│   │   ├── event_bus.h/cc
│   │   ├── session.h/cc
│   │   └── config.h/cc
│   │
│   ├── audio/                     # 模块1：听觉
│   │   ├── audio_codec.h/cc
│   │   ├── audio_pipeline.h/cc
│   │   ├── codecs/
│   │   ├── wake_word.h/cc
│   │   └── audio_processor.h/cc
│   │
│   ├── vision/                    # 模块2：视觉
│   │   ├── camera.h/cc
│   │   ├── camera_ov2640.h/cc
│   │   └── image_encoder.h/cc
│   │
│   ├── motion/                    # 模块3：运动
│   │   ├── actuator.h/cc
│   │   ├── servo.h/cc
│   │   ├── motor.h/cc
│   │   ├── servo_driver.h/cc
│   │   ├── imu.h/cc
│   │   └── obstacle.h/cc
│   │
│   ├── output/                    # 模块4：输出
│   │   ├── player.h/cc
│   │   ├── display.h/cc
│   │   ├── emotion.h/cc
│   │   └── led_indicator.h/cc
│   │
│   ├── comm/                      # 模块5：通信
│   │   ├── wifi_manager.h/cc
│   │   ├── agent_client.h/cc
│   │   ├── http_client.h/cc
│   │   └── web_server.h/cc
│   │
│   └── hal/                       # 硬件抽象层
│       ├── board.h/cc
│       ├── boards/
│       ├── i2c_bus.h/cc
│       ├── spi_bus.h/cc
│       └── pwm.h/cc
│
├── managed_components/
├── partitions/
├── CMakeLists.txt
├── sdkconfig.defaults
└── Kconfig.projbuild
```

---

## 模块开发状态

| 模块 | 状态 | 来源 | 优先级 |
|------|------|------|--------|
| 🎤 Audio | 🟡 可搬 | 小智代码 ~80% 可用 | P0（先搞） |
| 👁️ Vision | 🔴 待写 | 全新，参考 ESP-IDF camera 例程 | P1（阶段二） |
| 🦵 Motion | 🔴 待写 | 全全新，参考 PCA9685/MPU6050 库 | P2（阶段三） |
| 🔈 Output | 🟡 可搬 | 小智显示+LED ~70%，播放器需新写 | P0 |
| 📡 Comm | 🔴 待写 | WiFi 搬小智，Agent API 全新 | P0 |
| ⚙️ Core | 🟡 参考 | 状态机搬小智，事件总线/会话管理全新 | P0 |
| 🔧 HAL | 🟡 可搬 | Board/Button/WiFi 搬小智 | P0 |

**P0 = 第一批搭骨架，P1 = 阶段二填充，P2 = 阶段三填充**

---

## 开发计划

### 第一轮：骨架搭建（当前）
1. 创建项目目录结构
2. 搬 HAL 层（Board、Button、WiFi、Codec）
3. 写 Core 层骨架（状态机、事件总线、配置）
4. 写 Audio 模块骨架（接口+搬驱动）
5. 写 Output 模块骨架（接口+搬 LED）
6. 写 Comm 模块骨架（WiFi 搬过来 + Agent API 接口）
7. 写 Vision 模块骨架（纯接口，空实现）
8. 写 Motion 模块骨架（纯接口，空实现）
9. 确保能编译通过

### 第二轮：填充听觉链路
10. Agent API ASR 实现
11. Agent API Chat SSE 实现
12. Agent API TTS 实现
13. 按钮触发录音→ASR→Chat→TTS→播放 全链路跑通

### 第三轮：填充视觉链路
14. OV2640 驱动
15. 图像采集+JPEG 编码
16. Agent 视觉理解 API

### 第四轮：填充运动链路
17. PCA9685 舵机驱动
18. 直流电机驱动
19. Agent 动作执行 API

---

*文档版本：v1.0 | 2026-06-10 | 小希固件全模块架构*
