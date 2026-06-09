# 小智 ESP32 固件架构分析

> 基于 [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) v2.2.6 固件的代码分析
> 目标：设计一个新的开源 ESP32-S3 语音助手，通过Hermes Agent后端接入AI能力，不需要自建后端

---

## 1. 项目目录结构

```
xiaozhi-esp32/
├── CMakeLists.txt              # 顶层编译文件（ESP-IDF项目）
├── main/
│   ├── CMakeLists.txt          # 源文件列表、板子选择、字体/表情配置
│   ├── main.cc                 # 入口函数（app_main → Application::Initialize → Run）
│   ├── application.h/cc        # ★ 核心：主事件循环、状态机、协议调度
│   ├── device_state.h          # 设备状态枚举（空闲、听、说 等）
│   ├── device_state_machine.h  # 状态机，带状态切换校验 + 观察者模式
│   ├── settings.h              # 基于NVS的键值存储配置
│   ├── system_info.h           # MAC地址、内存、芯片型号等工具函数
│   ├── ota.h                   # OTA固件升级 + 设备激活逻辑
│   ├── mcp_server.h            # 设备端 MCP（Model Context Protocol）工具服务器
│   ├── assets.h                # SPIFFS/LVGL 资源管理（字体、表情、语音识别模型）
│   ├── audio/
│   │   ├── audio_codec.h       # ★ 音频编解码抽象基类（I2S输入/输出、采样率、音量）
│   │   ├── audio_service.h     # ★ 音频管线调度器（编解码队列、唤醒词、VAD）
│   │   ├── audio_processor.h   # 抽象基类：基于AFE的音频处理（回声消除、降噪、VAD）
│   │   ├── wake_word.h         # 抽象基类：唤醒词检测
│   │   ├── codecs/             # ES8311、ES8374、ES8388、ES8389、Box、Dummy 等编解码驱动
│   │   ├── processors/         # AfeAudioProcessor（ESP-SR AFE）、NoAudioProcessor
│   │   ├── wake_words/         # EspWakeWord（WakeNet）、AfeWakeWord（AFE+WakeNet）、自定义唤醒词
│   │   └── demuxer/            # OggDemuxer（OGG/OPUS流式解封装）
│   ├── boards/
│   │   ├── common/             # ★ 板子公共基础设施
│   │   │   ├── board.h         # 抽象Board单例（工厂模式，create_board）
│   │   │   ├── wifi_board.h    # WiFi板子基类（WiFi管理、配网模式、网络事件）
│   │   │   ├── ml307_board.h   # 4G蜂窝板子基类
│   │   │   ├── button.h        # 按钮驱动（消抖，支持单击/双击/长按）
│   │   │   ├── backlight.h     # PWM背光控制
│   │   │   ├── camera.h        # 摄像头接口
│   │   │   └── ...             # 电池、旋钮、定时关机、电源管理
│   │   └── <board-name>/       # 80多个板子配置（config.h + board.cc + 可选驱动）
│   ├── display/
│   │   ├── display.h           # ★ 显示抽象基类（SetStatus、SetEmotion、SetChatMessage）
│   │   ├── lcd_display.h       # SPI/RGB/MIPI LCD屏（基于LVGL）
│   │   ├── oled_display.h      # OLED屏（基于LVGL，128x64、128x32）
│   │   ├── emote_display.h     # ESP Emote表情显示
│   │   └── lvgl_display/       # LVGL主题、字体、图片、GIF解码、JPEG
│   ├── led/
│   │   ├── led.h               # LED抽象接口
│   │   ├── single_led.h        # 单个GPIO/LED灯带
│   │   ├── circular_strip.h    # 环形LED灯带（类似Echo的灯环）
│   │   └── gpio_led.h          # 简单GPIO LED
│   └── protocols/
│       ├── protocol.h          # ★ 协议抽象基类（音频通道、收发回调）
│       ├── websocket_protocol.h # WebSocket实现（二进制协议 v1/v2/v3）
│       └── mqtt_protocol.h     # MQTT + UDP实现（带AES加密）
├── managed_components/         # ESP-IDF托管组件（自动下载）
├── partitions/                 # 分区表（v1: 4MB，v2: 16MB）
├── sdkconfig.defaults*         # 各芯片的默认配置（esp32、esp32s3、esp32c3 等）
├── scripts/                    # 音频工具、图片转换、SPIFFS打包
└── docs/                       # 硬件文档（v0、v1）
```

### 编译系统
- **ESP-IDF** (≥5.5.2) + CMake
- 板子通过 `CONFIG_BOARD_TYPE_*` Kconfig选项选择
- 每个板子是 `main/boards/` 下的一个独立目录
- 通过 ESP 组件注册表（`idf_component.yml`）管理依赖组件
- 分区布局：OTA A/B双分区 + 8MB SPIFFS存储资源（字体、表情、语音识别模型）

---

## 2. 可复用的组件（直接拿来用或稍作修改）

### 2.1 音频编解码抽象层 (`main/audio/audio_codec.h`)
**结论：✅ 直接复用**

干净的I2S音频输入/输出抽象接口：
- `InputData()` / `OutputData()` — PCM读写
- `SetOutputVolume()`、`SetInputGain()`、`EnableInput/Output()`
- 暴露 `input_sample_rate`、`output_sample_rate`、`input_channels`、`output_channels`
- 内置 ES8311、ES8374、ES8388、ES8389 的实现（都是常用I2S编解码芯片）

### 2.2 音频编解码驱动 (`main/audio/codecs/`)
**结论：✅ 直接复用**

每个编解码驱动封装了ESP-IDF的 `esp_codec_dev` 库：
- `Es8311AudioCodec` — 最常用，ESP-BOX等板子用
- `Es8388AudioCodec` — 很多板子用
- `BoxAudioCodec` — ES8311+ES7210组合（麦克风阵列）
- `DummyAudioCodec` — 测试用

这些都是纯硬件驱动，不依赖后端服务器。

### 2.3 板子抽象层 (`main/boards/common/board.h`)
**结论：✅ 复用模式，适当简化**

Board单例 + 工厂模式设计得很好：
```cpp
static Board& GetInstance() {
    static Board* instance = static_cast<Board*>(create_board());
    return *instance;
}
#define DECLARE_BOARD(BOARD_CLASS_NAME) void* create_board() { return new BOARD_CLASS_NAME(); }
```

需要保留的关键虚方法：
- `GetAudioCodec()`、`GetDisplay()`、`GetLed()`、`GetBacklight()`
- `GetNetwork()`、`StartNetwork()`
- `GetBatteryLevel()`、`GetTemperature()`

**可以去掉的**：`GetBoardJson()`、`GetDeviceStatusJson()`（这些是给后端服务器上报用的）

### 2.4 WiFi板子基类 (`main/boards/common/wifi_board.h`)
**结论：✅ 基本全部复用**

使用 `78/esp-wifi-connect` 托管组件（WifiManager、SsidManager）：
- 自动WiFi配网（热点模式 + 强制门户页面）
- BluFi配网支持
- 声波配网（通过扬声器/麦克风）
- 连接超时 → 自动进入配网模式

WiFi基础设施完全独立于后端协议。

### 2.5 按钮、背光、LED
**结论：✅ 直接复用**

- `Button` — 消抖GPIO，支持单击/双击/长按回调
- `Backlight` (PwmBacklight) — 亮度控制，NVS持久化
- `Led` / `SingleLed` / `CircularStrip` / `GpioLed` — LED状态指示

### 2.6 显示系统
**结论：✅ 直接复用**

清晰的继承层次：`Display` → `LvglDisplay` → `LcdDisplay` / `OledDisplay`
- 基于LVGL的UI，带主题、表情、状态栏
- 支持SPI LCD、RGB LCD、MIPI LCD、OLED等多种屏幕
- `DisplayLockGuard` 线程安全的LVGL访问

### 2.7 配置系统 (NVS)
**结论：✅ 直接复用**

简单的NVS封装：`GetString()`、`SetString()`、`GetInt()`、`SetBool()` 等
支持命名空间（如 "websocket"、"mqtt"）— 非常适合存储Agent后端地址、API Key等配置。

### 2.8 设备状态机
**结论：✅ 复用模式**

设计精良的状态机：
- 带校验的状态切换（防止非法状态变更）
- 观察者模式（状态变化回调）
- 状态：`Unknown → Starting → Idle → Connecting → Listening → Speaking`

### 2.9 OGG解封装器
**结论：✅ 直接复用**

流式OGG/Opus解封装器 — 用于播放Agent后端返回的Opus音频。

### 2.10 MCP服务器
**结论：✅ 直接复用（可选）**

设备端MCP工具服务器。可用于LLM触发的本地工具执行。

---

## 3. 需要重写的组件

### 3.1 协议层 (`main/protocols/`)
**结论：🔄 完全重写**

**现有架构**（小智原版）：
- WebSocket连接到小智后端服务器
- 服务器负责：语音识别(ASR) → 大模型(LLM) → 语音合成(TTS)，把Opus音频发回来
- 自定义二进制协议（v1/v2/v3）
- JSON控制消息（hello、listen、abort、mcp）
- MQTT + UDP变体（蜂窝网络用）

**新架构**（接入Hermes Agent后端）：
- 通过WebSocket连接到Hermes Agent后端
- 后端统一处理ASR→LLM→TTS，设备端只管收音和播放
- 两种模式：
  1. **WebSocket模式**：录音 → Opus编码 → 发送到Hermes Agent后端 → 后端完成ASR+LLM+TTS → 返回音频 → 播放
  2. **实时模式**：OpenAI Realtime API WebSocket（可选，延迟更低）

**需要新建的**：
- `AgentProtocol` — WebSocket客户端，连接Hermes Agent后端
- `AgentRealtimeProtocol` — WebSocket客户端（实时模式，可选）
- ASR在Agent后端完成，设备端不直接调
- TTS在Agent后端完成，设备端只播放返回的音频

### 3.2 OTA系统
**结论：🔄 重写（去掉设备激活机制）**

现有OTA从小智后端检查版本，并且需要设备激活。新版应该：
- 使用标准ESP-IDF OTA（HTTPS固件下载）
- 自建更新服务器或用GitHub Releases
- 去掉激活/设备绑定逻辑

### 3.3 Application.cc 调度逻辑
**结论：🔄 部分重写**

核心事件循环和状态机可以复用，但：
- 去掉：`InitializeProtocol()`（连接小智后端）
- 去掉：`ShowActivationCode()`（设备激活流程）
- 去掉：`CheckAssetsVersion()` / `CheckNewVersion()`（依赖后端的版本检查）
- 重写：`HandleNetworkConnectedEvent()` — 网络连上后连接Hermes Agent后端
- 重写：音频通道打开/关闭 — 现在是每次请求独立的，而不是持久连接

### 3.4 唤醒词集成
**结论：🔄 调整适配**

现有唤醒词使用ESP-SR（WakeNet + AFE），这是**乐鑫私有的**（部分模型需要NDA授权）。可选方案：
1. 如果只针对ESP32-S3，继续用ESP-SR（公开模型可用）
2. 换成更简单的关键词检测（比如按钮触发，或者外部PDM麦克风 + 云端唤醒词）
3. 使用 `custom_wake_word.h` 方案（服务器端唤醒词检测）

---

## 4. 硬件抽象层

### 板子定义模式
每个板子是 `main/boards/<name>/` 下的一个目录，包含：

| 文件 | 用途 |
|------|------|
| `config.h` | 引脚定义、采样率、屏幕尺寸 |
| `config.json` | 板子元数据（用于网页配置/文档） |
| `<name>.cc` | 板子类实现（构造函数初始化硬件） |
| `power_manager.h` | 可选：电池/电源管理 |
| 自定义驱动 | 可选：LCD驱动、音频编解码等 |

**板子config.h示例**（ESP-BOX-3）：
```cpp
#define AUDIO_INPUT_SAMPLE_RATE  24000
#define AUDIO_I2S_GPIO_MCLK GPIO_NUM_2
#define AUDIO_CODEC_ES8311_ADDR  ES8311_CODEC_DEFAULT_ADDR
#define DISPLAY_WIDTH   320
#define DISPLAY_HEIGHT  240
#define BOOT_BUTTON_GPIO        GPIO_NUM_0
```

**板子类示例**（ESP-BOX-3）：
```cpp
class EspBox3Board : public WifiBoard {
    // 构造函数中初始化 I2C、SPI、屏幕、按钮
    // 重写 GetAudioCodec() → 返回 BoxAudioCodec
    // 重写 GetDisplay() → 返回 SpiLcdDisplay
};
DECLARE_BOARD(EspBox3Board);  // 注册工厂函数
```

### 支持的硬件（80多个板子）
**ESP32系列芯片**：ESP32、ESP32-S3、ESP32-C3、ESP32-C5、ESP32-C6、ESP32-P4

**热门板子**：ESP-BOX、ESP-BOX-3、M5Stack CoreS3/Cardputer、微雪系列、星智魔方、LilyGo显示屏、AtomS3、DFRobot K10 等众多社区板子

**音频编解码芯片**：ES8311、ES8374、ES8388、ES8389、ES7210、内置ADC/PDM

**屏幕**：ILI9341、GC9A01、ST7789、SSD1306、SH8601、AXS15231B、各种AMOLED/电子纸

**网络**：WiFi（所有芯片）、4G蜂窝（ML307、NT26）、USB RNDIS、以太网

---

## 5. 协议分析

### WebSocket二进制协议

固件支持3种协议版本的二进制音频帧：

**版本1**（原始）：WebSocket二进制帧里直接放原始Opus字节。

**版本2**（`BinaryProtocol2`，16字节头部）：
```
┌──────────┬──────────┬──────────┬──────────┬──────────┬─────────┐
│ 版本号    │ 类型      │ 保留      │ 时间戳    │ 载荷大小  │ 载荷     │
│ 2字节    │ 2字节     │ 4字节     │ 4字节     │ 4字节     │ N字节   │
│ 网络序    │ 网络序    │ 网络序    │ 网络序    │ 网络序    │         │
└──────────┴──────────┴──────────┴──────────┴──────────┴─────────┘
```
- `type`：0 = OPUS音频，1 = JSON（文本控制消息）

**版本3**（`BinaryProtocol3`，4字节头部）：
```
┌──────────┬──────────┬──────────┬─────────┐
│ 类型      │ 保留      │ 载荷大小  │ 载荷     │
│ 1字节    │ 1字节     │ 2字节     │ N字节   │
└──────────┴──────────┴──────────┴─────────┘
```

### JSON控制消息（设备 → 服务器）

| 类型 | 方向 | 字段 | 用途 |
|------|------|------|------|
| `hello` | → 服务器 | version、features、transport、audio_params | 握手 |
| `hello` | ← 客户端 | session_id、audio_params (采样率、帧时长) | 服务器应答 |
| `listen` | → 服务器 | state: detect/start/stop、mode: auto/manual/realtime、text | 监听控制 |
| `abort` | → 服务器 | reason: wake_word_detected | 中止播报 |
| `mcp` | → 服务器 | payload (JSON-RPC) | MCP工具调用 |

### 音频参数
- **格式**：Opus（编码后）
- **采样率**：16kHz（设备端）→ 24kHz（服务器输出，可配置）
- **声道**：1（单声道）
- **帧时长**：60ms（可配置：5/10/20/40/60/80/100/120ms）
- **码率**：自动（VBR，开启DTX）

---

## 6. 第三方依赖

### ESP-IDF组件（通过组件注册表）

| 组件 | 用途 | 许可证 |
|------|------|--------|
| `espressif/esp-sr` | 语音识别（WakeNet、AFE、AEC、NS、VAD） | 乐鑫私有 |
| `espressif/esp_audio_codec` | 音频编解码抽象 | Apache-2.0 |
| `espressif/esp_codec_dev` | 编解码设备驱动框架 | Apache-2.0 |
| `espressif/esp-dsp` | DSP库（FFT等） | Apache-2.0 |
| `espressif/button` | 按钮驱动（消抖） | Apache-2.0 |
| `espressif/led_strip` | WS2812/NeoPixel灯带驱动 | Apache-2.0 |
| `espressif/knob` | 旋钮编码器驱动 | Apache-2.0 |
| `espressif/esp_lcd_*` | LCD屏驱动（ILI9341、GC9A01、ST7789等） | Apache-2.0 |
| `espressif/esp_lcd_touch_*` | 触摸屏驱动（CST816S、FT5x06、GT911） | Apache-2.0 |
| `espressif/esp_lvgl_port` | LVGL的ESP-IDF移植层 | MIT |
| `lvgl/lvgl` | LVGL图形库 | MIT |
| `espressif/freetype` | FreeType字体渲染 | Apache-2.0 |
| `78/esp-wifi-connect` | WiFi管理（连接、AP、强制门户） | MIT |
| `78/xiaozhi-fonts` | 中文/表情字体 | 自定义(78) |
| `78/esp-ml307` | ML307 4G模块驱动 | MIT |
| `laride/heatshrink` | Heatshrink压缩算法 | ISC |

### 新项目的许可证注意事项
- **ESP-SR**（唤醒词、AFE）：乐鑫私有 — 使用ESP-IDF即可免费使用，但模型文件的再分发可能受限。**如果要做完全开源项目，需要考虑替代方案**
- **其他所有组件**：Apache-2.0 或 MIT — 开源安全
- **小智ESP32本身**：MIT许可证 ✅

---

## 7. 配置系统

### 基于NVS的设置 (`main/settings.h`)
```cpp
Settings settings("websocket", false);  // 命名空间, 是否只读
std::string url = settings.GetString("url");
std::string token = settings.GetString("token");
int version = settings.GetInt("version");
```

**现有的命名空间**：
- `websocket` — url、token、version
- `mqtt` — server、port、client_id、username、password
- 通用NVS存储WiFi凭据（由WifiManager/SsidManager管理）

### 新项目的配置
在NVS中用一个命名空间（如 `"config"`）存储：
- `agent_url` — Hermes Agent后端地址（如 `ws://192.168.1.11:8000/xiaozhi/v1/`）
- `api_key` — API密钥
- `model` — 模型名称（如 `deepseek-chat`）
- TTS在Agent后端完成，设备端不需要单独配置
- `tts_voice` — 音色名称（如 `alloy`）
- `stt_url` — STT端点（可选，默认用Whisper）
- `system_prompt` — 自定义系统提示词
- `language` — 语言代码
- `wake_word_enabled` — 是否启用唤醒词

---

## 8. 音频管线

### 数据流架构
```
麦克风 → I2S接收 → [音频编解码] → PCM
                                    ↓
                        ┌─── 唤醒词检测（始终运行）
                        │
                        ↓
                   [音频处理器]（AFE：回声消除 + 降噪 + VAD）
                        ↓
                   干净的PCM（16kHz，单声道）
                        ↓
                  ┌─ 编码队列 → [Opus编码器] → 发送队列 → 服务器
                  │
                  └─ （用于服务器端AEC：时间戳跟踪）

服务器 → Opus包 → 解码队列 → [Opus解码器] → 播放队列 → 扬声器
```

### 关键参数
| 参数 | 值 | 说明 |
|------|-----|------|
| 输入采样率 | 16kHz 或 24kHz | 取决于板子 |
| 输出采样率 | 16kHz 或 24kHz | 取决于板子 |
| 编码采样率 | 16kHz | 上传固定 |
| 编码格式 | Opus | VBR、DTX、complexity=0 |
| 帧时长 | 60ms | 16kHz下960个采样点 |
| 解码采样率 | 24kHz | 服务器输出（协商决定） |
| 重采样 | 内置 | `esp_ae_rate_cvt` 用于输入/输出采样率转换 |

### 线程模型
| 任务 | 优先级 | 用途 |
|------|--------|------|
| `audio_input` | 高 | 读取麦克风，喂给唤醒词和处理器 |
| `audio_output` | 高 | 写PCM到扬声器 |
| `opus_codec` | 中 | 编码麦克风PCM / 解码服务器Opus |
| 主任务 | 正常 | 事件循环、状态机、协议 |

### 新项目的音频流
如果接入Hermes Agent后端，流程变为：
```
麦克风 → [音频编解码] → PCM → [唤醒词/VAD] → 收集完整语音
                                                    ↓
                                          [Opus/PCM编码器]
                                                    ↓
                                     HTTP POST 到 /v1/audio/transcriptions（Whisper）
                                                    ↓
                                                 文字
                                                    ↓
                               HTTP POST /v1/chat/completions（流式SSE）
                                                    ↓
                                                 文字片段
                                                    ↓
                                     HTTP POST /v1/audio/speech（TTS）
                                                    ↓
                                          Opus/MP3/PCM 音频
                                                    ↓
                                          [解码器] → 扬声器
```

另一种方案：**OpenAI Realtime API** 使用单个WebSocket双向传输音频（类似小智现有方式，直接连Hermes Agent后端）。

---

## 9. 关键文件速查表

### 核心架构（必读）

| 文件 | 行数 | 说明 |
|------|------|------|
| `main/application.h` | 193 | 主应用类 — 事件循环、状态管理、协议生命周期 |
| `main/application.cc` | 1131 | 完整实现 — **最重要的文件** |
| `main/protocols/protocol.h` | 98 | 协议抽象接口 — 音频通道、收发回调 |
| `main/protocols/websocket_protocol.cc` | 254 | WebSocket实现 — **理解协议必看** |
| `main/audio/audio_service.h` | 194 | 音频管线调度器 — 编解码队列、线程 |
| `main/audio/audio_codec.h` | 61 | 音频编解码抽象接口 |
| `main/boards/common/board.h` | 92 | 板子单例工厂模式 |
| `main/boards/common/wifi_board.cc` | 357 | WiFi板子实现 — 连接、配网模式 |
| `main/device_state_machine.h` | 83 | 状态机，带切换校验 |
| `main/settings.h` | 28 | NVS配置封装 |

### 板子参考（新板子开发参考）

| 文件 | 说明 |
|------|------|
| `main/boards/esp-box-3/config.h` | 干净的板子配置示例（ESP-BOX-3） |
| `main/boards/esp-box-3/esp_box3_board.cc` | 完整的板子实现（I2C、SPI、LCD、按钮） |
| `main/boards/bread-compact-wifi/config.h` | 最简WiFi板子配置 |
| `main/boards/common/button.h` | 按钮抽象（带回调） |
| `main/boards/common/backlight.h` | PWM背光控制 |

### 音频管线（理解编解码）

| 文件 | 说明 |
|------|------|
| `main/audio/codecs/es8311_audio_codec.h` | 最常用的编解码驱动模式 |
| `main/audio/processors/afe_audio_processor.h` | AFE音频处理器（回声消除、降噪、VAD） |
| `main/audio/wake_words/afe_wake_word.h` | 基于AFE的唤醒词检测 |
| `main/audio/demuxer/ogg_demuxer.h` | OGG/Opus流式解封装器 |

### 显示系统（可选，用于视觉反馈）

| 文件 | 说明 |
|------|------|
| `main/display/display.h` | 显示抽象接口 |
| `main/display/lcd_display.h` | LCD显示屏（基于LVGL） |
| `main/display/oled_display.h` | OLED显示屏（基于LVGL） |

---

## 10. 新项目推荐架构

### 简化的模块结构
```
esp32-voice-assistant/
├── main/
│   ├── main.cc
│   ├── app/
│   │   ├── application.h/cc        # 事件循环（复用小智模式）
│   │   ├── device_state.h          # 状态机（直接复用）
│   │   └── settings.h              # NVS配置（直接复用）
│   ├── audio/
│   │   ├── audio_codec.h           # 复用小智的音频抽象接口
│   │   ├── codecs/                 # 复用小智的编解码驱动
│   │   ├── audio_pipeline.h/cc     # 新建：简化的 麦克风→编码→发送到Agent→解码→扬声器
│   │   └── opus_codec.h/cc         # 新建：独立的Opus编解码封装
│   ├── api/
│   │   ├── agent_client.h/cc      # 新建：Hermes Agent WebSocket客户端
│   │   ├── agent_protocol.h/cc    # 新建：Agent通信协议实现
│   │   │   # ASR在Agent后端完成，设备端不需要
│   │   └── audio_player.h/cc      # 新建：播放Agent返回的音频
│   ├── boards/
│   │   ├── board.h                 # 复用小智的板子抽象
│   │   ├── wifi_board.h            # 复用小智的WiFi板子
│   │   └── <board-name>/           # 复用小智的板子配置
│   ├── display/                    # 复用小智的显示系统
│   ├── led/                        # 复用小智的LED系统
│   └── ota.h/cc                    # 简化的OTA（去掉激活机制）
└── components/                     # 最少的托管组件
```

### 关键设计决策
1. **ESP32只管收音播放** — 所有智能在Hermes Agent后端
2. **Agent后端可切换** — 改地址就能换后端（Hermes、小智官方等）
3. **端点可配置** — 所有URL通过NVS/配置修改
4. **两种模式**：
   - REST模式（录音 → 识别 → 聊天 → TTS → 播放）— 更简单，延迟稍高
   - Realtime模式（OpenAI Realtime API WebSocket）— 可选，延迟更低
5. **保留小智的板子/显示/LED/音频编解码基础设施** — 这些设计得非常好
6. **替换协议层 + 应用调度** — 去掉对小智服务器的依赖，改为接入Hermes Agent

---

## 总结

**可复用的部分（70%以上的代码）**：
- 音频编解码抽象 + 所有编解码驱动
- 板子抽象 + WiFi板子 + 所有板子配置（引脚定义）
- 显示系统（基于LVGL的LCD/OLED）
- LED系统
- 按钮、背光、旋钮、电池监控
- 配置系统（NVS封装）
- 设备状态机
- OGG解封装器
- MCP服务器（可选）

**需要重写的部分（30%）**：
- 协议层 → Hermes Agent WebSocket客户端
- 应用调度 → 去掉服务器特定逻辑
- OTA → 去掉激活系统
- 音频管线 → 简化为发送到Agent后端

**最大的挑战**：ESP-SR唤醒词是乐鑫私有的。如果要做完全开源项目，考虑用按钮触发，或者使用不需要NDA的公开WakeNet模型。

---

*小希项目 (hermes-xiaoxi) · 基于小智ESP32固件分析 · 2026年6月*
