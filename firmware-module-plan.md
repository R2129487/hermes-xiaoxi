# 小希固件 · 模块复用清单

> 从 xiaozhi-esp32 中拆零件，搭咱们自己的架构
> 原则：借鉴小智的实现，架构是咱们自己的

---

## 总体策略

小智的代码是 **MIT 许可证**，可以自由使用和修改。但它的架构是"设备绑死后端"，咱们要改成"设备是哑巴终端，大脑在后端"。

**不做的事情：**
- ❌ 不 fork 小智仓库来改（改30%不如自己搭）
- ❌ 不用小智的 WebSocket 二进制协议（绑死后端）
- ❌ 不用小智的认证/设备管理（咱们不需要）
- ❌ 不用小智的 OTA 配置分发（咱们用 Web 页面）

**做的事情：**
- ✅ 搬小智的硬件驱动层（音频、显示、LED、按钮、WiFi）
- ✅ 搬小智的 Board 抽象模式（80+ 板子配置）
- ✅ 参考小智的状态机和事件驱动设计
- ✅ 自己写通信层（标准 HTTP，OpenAI 兼容 API）
- ✅ 自己写 Web 配置页面

---

## 模块拆解

### ✅ 直接搬（改命名空间即可）

| 模块 | 小智路径 | 说明 | 改动量 |
|------|---------|------|--------|
| **音频 Codec 抽象** | `main/audio/audio_codec.h/cc` | I2S 输入/输出的纯抽象基类 | 改 include 路径 |
| **Codec 驱动** | `main/audio/codecs/` | ES8311/8374/8388/8389 驱动 | 基本不改 |
| **Board 抽象** | `main/boards/common/board.h/cc` | Board 单例 + 工厂模式 | 删 GetBoardJson 等服务端方法 |
| **WiFi Board** | `main/boards/common/wifi_board.h/cc` | WiFi AP 配网、自动重连 | 基本不改 |
| **WiFi 管理（独立）** | `main/comm/wifi_manager.cc` | 从 wifi_board 拆出的独立 WiFi STA/AP 管理（含 WifiManager 类） | 🆕 自己新写 |
| **Button** | `main/boards/common/button.h/cc` | 按钮消抖、单击/双击/长按 | 不改 |
| **Backlight** | `main/boards/common/backlight.h/cc` | PWM 背光控制 | 不改 |
| **LED 驱动** | `main/led/` | 单 LED、灯环、GPIO LED | 不改 |
| **LVGL 显示** | `main/display/` | LCD/OLED/表情显示 | 删服务端消息显示 |
| **NVS 配置** | `main/settings.h/cc` | 键值对存储 | 不改 |
| **设备状态机** | `main/device_state_machine.h/cc` | 状态转换 + 观察者模式 | 不改 |
| **OGG Demuxer** | `main/audio/demuxer/` | 流式 OGG/Opus 解析 | 不改 |
| **雷达传感器接口** | `main/sensors/radar.h/cc` | 雷达抽象接口（超声波/毫米波/激光） | 不改 |

### ✅ 搬但需简化

| 模块 | 小智路径 | 改什么 |
|------|---------|--------|
| **AudioService** | `main/audio/audio_service.h/cc` | 删掉协议层绑定，只保留编解码+唤醒词+VAD 编排 |
| **Board 配置** | `main/boards/<name>/` | 只保留我们需要的几个板子（S3-BOX3、面包板套件等），删 80+ 个 |
| **ESP-SR 唤醒词** | `main/audio/wake_words/` | 保留 WakeNet + AFE，唤醒词改"你好小鑫" |
| **AFE 音频处理** | `main/audio/processors/` | 保留 AEC 回声消除 + 降噪 + VAD |
| **OTA** | `main/ota.h/cc` | 简化为纯固件 HTTP 升级，删激活/配置分发逻辑 |

### 🔄 参考但重写

| 模块 | 小智的做法 | 我们的做法 |
|------|----------|----------|
| **通信层 (Comm)** | 自定义 WebSocket 二进制协议（v1/v2/v3） | **标准 HTTP + OpenAI 兼容 API**；`AgentClient` 支持 4 个独立端点（Chat/ASR/TTS/Vision），也可共用同一地址 fallback |
| **ASR** | 音频发到服务器，服务器做 ASR | POST 音频到 `/v1/audio/transcriptions`（Whisper API） |
| **LLM** | 服务器代理调大模型 | POST 到 `/v1/chat/completions`（SSE 流式） |
| **TTS** | 服务器返回 Opus 音频 | POST 到 `/v1/audio/speech`，接收音频流播放 |
| **配置管理** | 智控台 Web 后端 | **ESP32 本地 Web 页面**（AP 热点 192.168.4.1） |
| **设备认证** | 设备 ID + Token + 服务器激活 | 不需要，填 API Key 即用 |

### ❌ 不搬

| 模块 | 原因 |
|------|------|
| `main/protocols/websocket_protocol.*` | 绑死小智二进制协议 |
| `main/protocols/mqtt_protocol.*` | 咱们不用 MQTT |
| `main/mcp_server.*` | MCP 设备端暂不需要 |
| `main/ota.cc` 中的激活逻辑 | 不需要设备激活 |
| 80+ 个板子配置 | 只保留 5-8 个常用的 |

---

## 新项目目录结构

```
xiaoxi-firmware/
├── main/
│   ├── main.cc                    # 入口（main.cc）
│   ├── core/                      # 核心层
│   │   ├── application.h/cc       # 主循环、事件调度；WiFi 等待循环（30秒）、AudioCodec 注入、Agent 端点分别配置
│   │   ├── config.h/cc            # 全局配置；新增 ModelEndpoint 结构体、codec_type、radar_type、I2S 引脚配置
│   │   ├── event_bus.h/cc         # 事件总线
│   │   ├── state_machine.h/cc     # 状态机（搬）
│   │   ├── session.h/cc           # 会话管理
│   │   └── voice_chain.h/cc       # 语音任务编排
│   │
│   ├── audio/                     # 音频子系统
│   │   ├── audio_codec.h/cc       # 抽象基类（搬）
│   │   ├── audio_pipeline.h/cc    # 音频管线；RecordUtterance 不再自己管录音开关
│   │   ├── board_bridge.h         # 音频板级桥接
│   │   ├── wake_word.h            # 唤醒词抽象
│   │   ├── codecs/                # ES8311/8374/8388/8389 等驱动（搬）
│   │   ├── processors/            # AFE（AEC+NS+VAD）（搬）
│   │   └── wake_words/            # WakeNet（搬，改唤醒词）
│   │
│   ├── comm/                      # 🆕 通信层（自己写）
│   │   ├── comm.h/cc              # AgentClient：支持 4 个独立端点（Chat/ASR/TTS/Vision）+ WebServer
│   │   └── wifi_manager.cc        # 🆕 WiFi STA/AP 独立管理，从 comm 拆分
│   │
│   ├── hal/                       # 硬件抽象层（搬+精简）
│   │   ├── board.h/cc             # Board 抽象（搬）
│   │   └── (button/backlight/LED) # 按钮、背光、LED 驱动
│   │
│   ├── output/                    # 输出子系统
│   │   └── output.h/cc            # LED 指示灯、播放器、显示
│   │
│   ├── sensors/                   # 🆕 传感器模块
│   │   └── radar.h/cc             # 雷达传感器接口（超声波/毫米波/激光）
│   │
│   ├── motion/                    # 🆕 运动控制模块（阶段三）
│   │   └── actuator.h/cc          # 舵机/电机/IMU 控制
│   │
│   ├── vision/                    # 🆕 视觉模块（阶段二）
│   │   └── camera.h/cc            # 摄像头驱动
│   │
│   └── stubs/                     # 临时桩（后续替换）
│       ├── assets.h
│       ├── board.h
│       ├── protocol.h
│       ├── settings.h
│       └── system_info.h
│
├── managed_components/            # ESP-IDF 组件
├── partitions/                    # 分区表
├── CMakeLists.txt
├── sdkconfig.defaults             # 默认配置
└── Kconfig.projbuild              # 自定义配置项
```

---

## 通信流程（新架构）

```
设备端                          Agent 后端
  │                                │
  │  1. 唤醒词检测 / 按钮按下         │
  │  → 开始录音 (I2S → PCM)         │
  │                                │
  │  2. POST /v1/audio/transcriptions  │
  │  ──── PCM/WAV 音频 ────────────▶  ASR 识别
  │  ◀──── 文本 "帮我查天气" ────────  │
  │                                │
  │  3. POST /v1/chat/completions      │
  │  ──── {"role":"user",           │
  │       "content":"帮我查天气"} ──▶  LLM 推理
  │  ◀──── SSE 流式文本 ────────────  │
  │                                │
  │  4. POST /v1/audio/speech          │
  │  ──── {"input":"今天晴天..."} ──▶  TTS 合成
  │  ◀──── Opus 音频流 ─────────────  │
  │                                │
  │  5. 播放音频 (Opus → I2S)        │
```

---

## 关键技术决策

### 为什么用 HTTP 而不是 WebSocket？
- OpenAI 标准 API 就是 HTTP，不用自己定义协议
- ESP-IDF 的 `esp_http_client` 成熟稳定
- SSE 流式足够用，不需要双向 WebSocket
- 设备端代码更简单，不需要维护长连接状态

### ASR 走哪个接口？
- **首选**：`/v1/audio/transcriptions`（Whisper API 格式）
- 本地 Whisper 服务或云端都支持这个接口
- ESP32 端录音完一次性 POST（不是流式），简单可靠

### TTS 走哪个接口？
- **首选**：`/v1/audio/speech`（OpenAI TTS API 格式）
- 备选：EdgeTTS（免费，HTTP GET 直接拿音频）
- GPT-SoVITS 的 API 格式需要适配（9880 端口）

### Web 配置页面怎么做？
- ESP32 上跑 `esp_http_server`（ESP-IDF 内置）
- AP 热点模式：ESP32 开热点，手机连上访问 192.168.4.1
- 配置项：WiFi SSID/密码、Agent 后端地址、API Key、模型名、音量
- HTML 页面直接编译进 Flash（用 EMBED_FILES）

---

## 开发顺序

### 第一步：最小可运行固件
1. 搬 Board + Audio Codec + WiFi（从面包板套件开始）
2. 实现按钮触发录音 → HTTP POST 到本地 LM Studio → 播放回复
3. 不要唤醒词、不要显示、不要 Web 配置
4. **目标：按下按钮说话，听到回复**

### 第二步：加 Web 配置
5. 实现 esp_http_server + AP 热点
6. 配置页面：WiFi、后端地址、API Key
7. NVS 持久化配置

### 第三步：加唤醒词
8. 搬 ESP-SR WakeNet + AFE
9. 切换唤醒词到"你好小鑫"
10. 唤醒词打断功能

### 第四步：加显示和表情
11. 搬 LVGL 显示系统
12. 状态显示（待机/录音/思考/播放）
13. 表情动画

### 第五步：适配多硬件
14. 加 S3-BOX3 板子配置
15. 加 ESP32-CAM 视觉版（阶段二）
16. 加 C3 笔形版

---

## 环境准备

```bash
# ESP-IDF 已装好（v5.5.2）
source ~/esp/esp-idf/export.sh

# 创建新项目
cd ~/xiaoxi-project
mkdir -p xiaoxi-firmware
cd xiaoxi-firmware
idf.py create-project .
# 然后逐步搬模块进来
```

---

*文档版本：v1.1 | 2026-06-10 | 小希固件模块复用清单 | 总源文件：62 个（.h + .cc/.cpp）*
