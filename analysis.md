# xiaozhi-esp32 Architecture Analysis

> Analysis of [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) v2.2.6 firmware for designing a new open-source ESP32-S3 voice assistant that connects to Hermes Agent backend for all AI capabilities.

---

## 1. Project Structure

```
xiaozhi-esp32/
├── CMakeLists.txt              # Top-level build (ESP-IDF project)
├── main/
│   ├── CMakeLists.txt          # Source file list, board selection, font/emoji config
│   ├── main.cc                 # Entry point (app_main → Application::Initialize → Run)
│   ├── application.h/cc        # ★ Core: main event loop, state machine, protocol orchestration
│   ├── device_state.h          # Device state enum (Idle, Listening, Speaking, etc.)
│   ├── device_state_machine.h  # State machine with transition validation + observer pattern
│   ├── settings.h              # NVS-based key-value settings
│   ├── system_info.h           # MAC, heap, chip model utilities
│   ├── ota.h                   # OTA firmware update + activation logic
│   ├── mcp_server.h            # MCP (Model Context Protocol) tool server on device
│   ├── assets.h                # SPIFFS/LVGL asset management (fonts, emoji, SR models)
│   ├── audio/
│   │   ├── audio_codec.h       # ★ Abstract base: I2S input/output, sample rate, volume
│   │   ├── audio_service.h     # ★ Audio pipeline orchestrator (encode/decode/WakeWord/VAD)
│   │   ├── audio_processor.h   # Abstract: AFE-based audio processing (AEC, NS, VAD)
│   │   ├── wake_word.h         # Abstract: wake word detection
│   │   ├── codecs/             # ES8311, ES8374, ES8388, ES8389, Box, Dummy, No codec
│   │   ├── processors/         # AfeAudioProcessor (ESP-SR AFE), NoAudioProcessor
│   │   ├── wake_words/         # EspWakeWord (WakeNet), AfeWakeWord (AFE+WakeNet), CustomWakeWord
│   │   └── demuxer/            # OggDemuxer (for OGG/OPUS playback)
│   ├── boards/
│   │   ├── common/             # ★ Shared board infrastructure
│   │   │   ├── board.h         # Abstract Board singleton (factory pattern via create_board)
│   │   │   ├── wifi_board.h    # WiFi board base (WifiManager, config mode, network events)
│   │   │   ├── ml307_board.h   # 4G cellular board base
│   │   │   ├── button.h        # Debounced button with click/double-click/long-press
│   │   │   ├── backlight.h     # PWM backlight control
│   │   │   ├── camera.h        # Camera interface
│   │   │   └── ...             # battery, knob, sleep timer, power management
│   │   └── <board-name>/       # ~80+ board configs (config.h + board.cc + optional drivers)
│   ├── display/
│   │   ├── display.h           # ★ Abstract Display base (SetStatus, SetEmotion, SetChatMessage)
│   │   ├── lcd_display.h       # SPI/RGB/MIPI LCD via LVGL
│   │   ├── oled_display.h      # OLED via LVGL (128x64, 128x32)
│   │   ├── emote_display.h     # ESP Emote expression display
│   │   └── lvgl_display/       # LVGL themes, fonts, images, GIF decoder, JPEG
│   ├── led/
│   │   ├── led.h               # Abstract LED interface
│   │   ├── single_led.h        # Single GPIO/LED strip
│   │   ├── circular_strip.h    # Circular LED strip (e.g., Echo-like ring)
│   │   └── gpio_led.h          # Simple GPIO LED
│   └── protocols/
│       ├── protocol.h          # ★ Abstract Protocol base (audio channel, send/receive)
│       ├── websocket_protocol.h # WebSocket implementation (Binary protocol v1/v2/v3)
│       └── mqtt_protocol.h     # MQTT + UDP implementation (with AES encryption)
├── managed_components/         # ESP-IDF managed components (auto-downloaded)
├── partitions/                 # Partition tables (v1: 4MB, v2: 16MB)
├── sdkconfig.defaults*         # Per-chip sdkconfig defaults (esp32, esp32s3, esp32c3, etc.)
├── scripts/                    # Audio tools, image converters, SPIFFS builders
└── docs/                       # Hardware docs (v0, v1)
```

### Build System
- **ESP-IDF** (≥5.5.2) with CMake
- Board selected via `CONFIG_BOARD_TYPE_*` Kconfig option
- Each board is a separate directory under `main/boards/`
- Managed components via ESP Component Registry (`idf_component.yml`)
- Partition layout: OTA A/B + 8MB SPIFFS for assets (fonts, emoji, SR models)

---

## 2. Reusable Components (Directly Borrow or Adapt)

### 2.1 Audio Codec Abstraction (`main/audio/audio_codec.h`)
**Verdict: ✅ REUSE AS-IS**

Clean abstract interface for I2S audio input/output:
- `InputData()` / `OutputData()` — PCM read/write
- `SetOutputVolume()`, `SetInputGain()`, `EnableInput/Output()`
- Exposes `input_sample_rate`, `output_sample_rate`, `input_channels`, `output_channels`
- Built-in implementations for ES8311, ES8374, ES8388, ES8389 (all common I2S codecs)

### 2.2 Audio Codec Drivers (`main/audio/codecs/`)
**Verdict: ✅ REUSE AS-IS**

Individual codec drivers wrap ESP-IDF's `esp_codec_dev` library:
- `Es8311AudioCodec` — most common, used by ESP-BOX, etc.
- `Es8388AudioCodec` — used by many boards
- `BoxAudioCodec` — ES8311+ES7210 combo (mic array)
- `DummyAudioCodec` — for testing

These are pure hardware drivers with no server dependency.

### 2.3 Board Abstraction (`main/boards/common/board.h`)
**Verdict: ✅ REUSE PATTERN, SIMPLIFY**

The Board singleton + factory pattern is excellent:
```cpp
static Board& GetInstance() {
    static Board* instance = static_cast<Board*>(create_board());
    return *instance;
}
#define DECLARE_BOARD(BOARD_CLASS_NAME) void* create_board() { return new BOARD_CLASS_NAME(); }
```
Key virtual methods to keep:
- `GetAudioCodec()`, `GetDisplay()`, `GetLed()`, `GetBacklight()`
- `GetNetwork()`, `StartNetwork()`
- `GetBatteryLevel()`, `GetTemperature()`

**Remove**: `GetBoardJson()`, `GetDeviceStatusJson()` (server-specific reporting)

### 2.4 WiFi Board Base (`main/boards/common/wifi_board.h`)
**Verdict: ✅ REUSE MOSTLY**

Uses `78/esp-wifi-connect` managed component (WifiManager, SsidManager):
- Automatic WiFi provisioning via captive portal (hotspot mode)
- BluFi provisioning support
- Acoustic WiFi provisioning (via speaker/mic)
- Connection timeout → config mode fallback

The WiFi infrastructure is fully independent of the backend protocol.

### 2.5 Button, Backlight, LED
**Verdict: ✅ REUSE AS-IS**

- `Button` — debounced GPIO with click/double-click/long-press callbacks
- `Backlight` (PwmBacklight) — brightness control with NVS persistence
- `Led` / `SingleLed` / `CircularStrip` / `GpioLed` — LED state indication

### 2.6 Display System
**Verdict: ✅ REUSE AS-IS**

Clean hierarchy: `Display` → `LvglDisplay` → `LcdDisplay` / `OledDisplay`
- LVGL-based UI with themes, emoji, status bar
- SPI LCD, RGB LCD, MIPI LCD, OLED variants
- `DisplayLockGuard` for thread-safe LVGL access

### 2.7 Settings (NVS)
**Verdict: ✅ REUSE AS-IS**

Simple NVS wrapper: `GetString()`, `SetString()`, `GetInt()`, `SetBool()`, etc.
Namespaced (e.g., "websocket", "mqtt") — perfect for storing Agent backend address, API keys.

### 2.8 Device State Machine
**Verdict: ✅ REUSE PATTERN**

Well-designed state machine with:
- Validated transitions (prevents illegal state changes)
- Observer pattern (callbacks on state change)
- States: `Unknown → Starting → Idle → Connecting → Listening → Speaking`

### 2.9 OGG Demuxer
**Verdict: ✅ REUSE AS-IS**

Streaming OGG/Opus demuxer — useful for playing back Opus audio from Agent backend.

### 2.10 MCP Server
**Verdict: ✅ REUSE AS-IS (optional)**

Device-side MCP tool server. Could be useful for local tool execution triggered by the LLM.

---

## 3. Components to Rewrite

### 3.1 Protocol Layer (`main/protocols/`)
**Verdict: 🔄 COMPLETE REWRITE**

**Current architecture** (xiaozhi-esp32):
- WebSocket connects to xiaozhi backend server
- Server does: STT → LLM → TTS, sends Opus audio back
- Binary protocol with custom framing (v1/v2/v3)
- JSON messages for control (hello, listen, abort, mcp)
- MQTT + UDP variant for cellular

**New architecture** (connect to Hermes Agent backend):
- WebSocket connection to Hermes Agent backend
- Backend handles ASR+LLM+TTS, device only records and plays
- Two modes:
  1. **WebSocket mode**: Record -> Opus encode -> send to Hermes Agent backend -> backend does ASR+LLM+TTS -> return audio -> play
  2. **Realtime mode**: OpenAI Realtime API WebSocket (optional, lower latency)

**What to build**:
- `AgentProtocol` — WebSocket client to connect Hermes Agent backend
- `AgentRealtimeProtocol` — WebSocket client for realtime mode (optional)
- ASR done by Agent backend, not on device
- TTS done by Agent backend, device only plays returned audio

### 3.2 OTA System
**Verdict: 🔄 REWRITE (remove server-specific activation)**

Current OTA checks xiaozhi backend for versions and requires device activation. New version should:
- Use standard ESP-IDF OTA (HTTPS firmware download)
- Self-hosted update server or GitHub Releases
- Remove activation/device binding logic

### 3.3 Application.cc Orchestration Logic
**Verdict: 🔄 PARTIAL REWRITE**

The core event loop and state machine are reusable, but:
- Remove: `InitializeProtocol()` (xiaozhi backend connection)
- Remove: `ShowActivationCode()` (device activation flow)
- Remove: `CheckAssetsVersion()` / `CheckNewVersion()` (backend-dependent)
- Rewrite: `HandleNetworkConnectedEvent()` — connect directly to API instead of backend
- Rewrite: Audio channel open/close — now it's per-request, not persistent

### 3.4 Wake Word Integration
**Verdict: 🔄 ADAPT**

Current wake word uses ESP-SR (WakeNet + AFE) which is **Espressif proprietary** (requires NDA for some models). Options:
1. Keep ESP-SR if targeting ESP32-S3 only (public models available)
2. Replace with a simpler keyword detection (e.g., button trigger, or external PDM mic + cloud wake word)
3. Use the `custom_wake_word.h` approach (server-side wake word detection)

---

## 4. Hardware Abstraction

### Board Definition Pattern
Each board is a directory under `main/boards/<name>/` containing:

| File | Purpose |
|------|---------|
| `config.h` | Pin definitions, sample rates, display geometry |
| `config.json` | Board metadata (for web config / documentation) |
| `<name>.cc` | Board class implementation (constructor initializes HW) |
| `power_manager.h` | Optional: battery/PMIC management |
| Custom drivers | Optional: LCD drivers, audio codecs, etc. |

**Board config.h example** (ESP-BOX-3):
```cpp
#define AUDIO_INPUT_SAMPLE_RATE  24000
#define AUDIO_I2S_GPIO_MCLK GPIO_NUM_2
#define AUDIO_CODEC_ES8311_ADDR  ES8311_CODEC_DEFAULT_ADDR
#define DISPLAY_WIDTH   320
#define DISPLAY_HEIGHT  240
#define BOOT_BUTTON_GPIO        GPIO_NUM_0
```

**Board class example** (ESP-BOX-3):
```cpp
class EspBox3Board : public WifiBoard {
    // Initialize I2C, SPI, Display, Buttons in constructor
    // Override GetAudioCodec() → returns BoxAudioCodec
    // Override GetDisplay() → returns SpiLcdDisplay
};
DECLARE_BOARD(EspBox3Board);  // Registers factory function
```

### Supported Hardware (~80+ boards)
**ESP32 variants**: ESP32, ESP32-S3, ESP32-C3, ESP32-C5, ESP32-C6, ESP32-P4

**Popular boards**: ESP-BOX, ESP-BOX-3, M5Stack CoreS3/Cardputer, Waveshare series, Xingzhi cubes, LilyGo displays, AtomS3, DFRobot K10, and many community boards.

**Audio codecs**: ES8311, ES8374, ES8388, ES8389, ES7210, internal ADC/PDM

**Displays**: ILI9341, GC9A01, ST7789, SSD1306, SH8601, AXS15231B, various AMOLED/ePaper

**Network**: WiFi (all chips), 4G cellular (ML307, NT26), USB RNDIS, Ethernet

---

## 5. Protocol Analysis

### WebSocket Binary Protocol

The firmware supports 3 protocol versions for binary audio framing:

**Version 1** (raw): Just raw Opus bytes in WebSocket binary frames.

**Version 2** (`BinaryProtocol2`, 16-byte header):
```
┌──────────┬──────────┬──────────┬──────────┬──────────┬─────────┐
│ version  │ type     │ reserved │timestamp │payload_sz│ payload │
│ 2 bytes  │ 2 bytes  │ 4 bytes  │ 4 bytes  │ 4 bytes  │ N bytes │
│ network  │ network  │ network  │ network  │ network  │         │
│ order    │ order    │ order    │ order    │ order    │         │
└──────────┴──────────┴──────────┴──────────┴──────────┴─────────┘
```
- `type`: 0 = OPUS audio, 1 = JSON (text control messages)

**Version 3** (`BinaryProtocol3`, 4-byte header):
```
┌──────────┬──────────┬──────────┬─────────┐
│ type     │ reserved │payload_sz│ payload │
│ 1 byte   │ 1 byte   │ 2 bytes  │ N bytes │
└──────────┴──────────┴──────────┴─────────┘
```

### JSON Control Messages (Protocol → Server)

| Type | Direction | Fields | Purpose |
|------|-----------|--------|---------|
| `hello` | → Server | version, features, transport, audio_params | Handshake |
| `hello` | ← Client | session_id, audio_params (sample_rate, frame_duration) | Server response |
| `listen` | → Server | state: detect/start/stop, mode: auto/manual/realtime, text | Listening control |
| `abort` | → Server | reason: wake_word_detected | Abort speaking |
| `mcp` | → Server | payload (JSON-RPC) | MCP tool calls |

### Audio Parameters
- **Format**: Opus (encoded)
- **Sample rate**: 16kHz (device) → 24kHz (server output, configurable)
- **Channels**: 1 (mono)
- **Frame duration**: 60ms (configurable: 5/10/20/40/60/80/100/120ms)
- **Bitrate**: Auto (VBR, DTX enabled)

---

## 6. Third-Party Dependencies

### ESP-IDF Components (via Component Registry)

| Component | Purpose | License |
|-----------|---------|---------|
| `espressif/esp-sr` | Speech recognition (WakeNet, AFE, AEC, NS, VAD) | Espressif proprietary |
| `espressif/esp_audio_codec` | Audio codec abstraction | Apache-2.0 |
| `espressif/esp_codec_dev` | Codec device driver framework | Apache-2.0 |
| `espressif/esp-dsp` | DSP library (FFT, etc.) | Apache-2.0 |
| `espressif/button` | Button driver with debounce | Apache-2.0 |
| `espressif/led_strip` | WS2812/NeoPixel driver | Apache-2.0 |
| `espressif/knob` | Rotary encoder driver | Apache-2.0 |
| `espressif/esp_lcd_*` | LCD panel drivers (ILI9341, GC9A01, ST7789, etc.) | Apache-2.0 |
| `espressif/esp_lcd_touch_*` | Touch screen drivers (CST816S, FT5x06, GT911) | Apache-2.0 |
| `espressif/esp_lvgl_port` | LVGL port for ESP-IDF | MIT |
| `lvgl/lvgl` | LVGL graphics library | MIT |
| `espressif/freetype` | FreeType font rendering | Apache-2.0 |
| `78/esp-wifi-connect` | WiFi management (connect, AP, captive portal) | MIT |
| `78/xiaozhi-fonts` | Chinese/emoji fonts | Custom (78) |
| `78/esp-ml307` | ML307 4G modem driver | MIT |
| `laride/heatshrink` | Heatshrink compression | ISC |

### License Summary for New Project
- **ESP-SR** (wake word, AFE): Proprietary Espressif — requires ESP-IDF, use is free but redistribution of models may be restricted. **Consider alternatives** for fully open-source project.
- **All other components**: Apache-2.0 or MIT — safe for open-source.
- **xiaozhi-esp32 itself**: MIT License ✅

---

## 7. Configuration System

### NVS-Based Settings (`main/settings.h`)
```cpp
Settings settings("websocket", false);  // namespace, read_only
std::string url = settings.GetString("url");
std::string token = settings.GetString("token");
int version = settings.GetInt("version");
```

**Current namespaces**:
- `websocket` — url, token, version
- `mqtt` — server, port, client_id, username, password
- General NVS for WiFi credentials (managed by WifiManager/SsidManager)

### For New Project
Store in NVS under a single namespace (e.g., `"config"`):
- `agent_url` — Hermes Agent backend address (e.g. `ws://192.168.1.11:8000/xiaozhi/v1/`)
- `api_key` — API key
- `model` — Model name (e.g., `deepseek-chat`)
- TTS handled by Agent backend, no separate config needed
- `tts_voice` — Voice name (e.g., `alloy`)
- `stt_url` — STT endpoint (optional, defaults to Whisper)
- `system_prompt` — Custom system prompt
- `language` — Language code
- `wake_word_enabled` — Whether to use wake word

---

## 8. Audio Pipeline

### Data Flow Architecture

```
MICROPHONE → I2S RX → [Audio Codec] → PCM
                                      ↓
                          ┌─── Wake Word Detection (always on)
                          │
                          ↓
                     [Audio Processor] (AFE: AEC + NS + VAD)
                          ↓
                     PCM (clean, 16kHz, mono)
                          ↓
                    ┌─ Encode Queue ─→ [Opus Encoder] ─→ Send Queue ─→ Server
                    │
                    └─ (for server AEC: timestamp tracking)

SERVER → Opus packets ─→ Decode Queue ─→ [Opus Decoder] ─→ Playback Queue ─→ Speaker
```

### Key Parameters
| Parameter | Value | Notes |
|-----------|-------|-------|
| Input sample rate | 16kHz or 24kHz | Board-dependent |
| Output sample rate | 16kHz or 24kHz | Board-dependent |
| Encoder sample rate | 16kHz | Fixed for upload |
| Encoder format | Opus | VBR, DTX, complexity=0 |
| Frame duration | 60ms | 960 samples at 16kHz |
| Decoder sample rate | 24kHz | Server output (negotiated) |
| Resampling | Built-in | `esp_ae_rate_cvt` for input/output rate conversion |

### Threading Model
| Task | Priority | Purpose |
|------|----------|---------|
| `audio_input` | High | Read mic, feed wake word + processor |
| `audio_output` | High | Write PCM to speaker |
| `opus_codec` | Medium | Encode mic PCM / Decode server Opus |
| Main task | Normal | Event loop, state machine, protocol |

### New Project Audio Flow
For Hermes Agent backend, the flow changes:
```
MIC → [Audio Codec] → PCM → [Wake Word / VAD] → collect utterance
                                                        ↓
                                              [Opus/PCM Encoder]
                                                        ↓
                                         HTTP POST to /v1/audio/transcriptions (Whisper)
                                                        ↓
                                                    text
                                                        ↓
                                    HTTP POST /v1/chat/completions (streaming SSE)
                                                        ↓
                                                    text chunks
                                                        ↓
                                         HTTP POST /v1/audio/speech (TTS)
                                                        ↓
                                              Opus/MP3/PCM audio
                                                        ↓
                                              [Decoder] → Speaker
```

Alternative: **OpenAI Realtime API** uses a single WebSocket with bidirectional audio (similar to xiaozhi, connected to Hermes Agent backend).

---

## 9. Key Files to Study

### Core Architecture (Must Read)

| File | Lines | Description |
|------|-------|-------------|
| `main/application.h` | 193 | Main application class — event loop, state management, protocol lifecycle |
| `main/application.cc` | 1131 | Full implementation — **the most important file** |
| `main/protocols/protocol.h` | 98 | Abstract protocol interface — audio channel, send/receive callbacks |
| `main/protocols/websocket_protocol.cc` | 254 | WebSocket implementation — **study for protocol understanding** |
| `main/audio/audio_service.h` | 194 | Audio pipeline orchestrator — encode/decode queues, threading |
| `main/audio/audio_codec.h` | 61 | Audio codec abstract interface |
| `main/boards/common/board.h` | 92 | Board singleton factory pattern |
| `main/boards/common/wifi_board.cc` | 357 | WiFi board implementation — connection, config mode |
| `main/device_state_machine.h` | 83 | State machine with transition validation |
| `main/settings.h` | 28 | NVS settings wrapper |

### Board Reference (Study for New Board Support)

| File | Description |
|------|-------------|
| `main/boards/esp-box-3/config.h` | Clean board config example (ESP-BOX-3) |
| `main/boards/esp-box-3/esp_box3_board.cc` | Complete board implementation with I2C, SPI, LCD, buttons |
| `main/boards/bread-compact-wifi/config.h` | Minimal WiFi board config |
| `main/boards/common/button.h` | Button abstraction with callbacks |
| `main/boards/common/backlight.h` | PWM backlight control |

### Audio Pipeline (Understand Encoding/Decoding)

| File | Description |
|------|-------------|
| `main/audio/codecs/es8311_audio_codec.h` | Most common codec driver pattern |
| `main/audio/processors/afe_audio_processor.h` | AFE audio processor (AEC, NS, VAD) |
| `main/audio/wake_words/afe_wake_word.h` | AFE-based wake word detection |
| `main/audio/demuxer/ogg_demuxer.h` | OGG/Opus streaming demuxer |

### Display (Optional, for Visual Feedback)

| File | Description |
|------|-------------|
| `main/display/display.h` | Abstract display interface |
| `main/display/lcd_display.h` | LCD display with LVGL |
| `main/display/oled_display.h` | OLED display with LVGL |

---

## 10. Recommended Architecture for New Project

### Simplified Module Structure
```
esp32-voice-assistant/
├── main/
│   ├── main.cc
│   ├── app/
│   │   ├── application.h/cc        # Event loop (reuse xiaozhi pattern)
│   │   ├── device_state.h          # State machine (reuse as-is)
│   │   └── settings.h              # NVS config (reuse as-is)
│   ├── audio/
│   │   ├── audio_codec.h           # Reuse xiaozhi abstract interface
│   │   ├── codecs/                 # Reuse xiaozhi codec drivers
│   │   ├── audio_pipeline.h/cc     # NEW: simplified mic→encode→API→decode→speaker
│   │   └── opus_codec.h/cc         # NEW: standalone Opus encode/decode wrapper
│   ├── api/
│   │   ├── agent_client.h/cc      # NEW: Hermes Agent WebSocket client
│   │   ├── agent_protocol.h/cc    # NEW: Agent communication protocol
│   │   ├── whisper_client.h/cc     # NEW: STT via Whisper API
│   │   └── audio_player.h/cc      # NEW: Play audio returned by Agent
│   ├── boards/
│   │   ├── board.h                 # Reuse xiaozhi board abstraction
│   │   ├── wifi_board.h            # Reuse xiaozhi WiFi board
│   │   └── <board-name>/           # Reuse xiaozhi board configs
│   ├── display/                    # Reuse xiaozhi display system
│   ├── led/                        # Reuse xiaozhi LED system
│   └── ota.h/cc                    # Simplified OTA (no activation)
└── components/                     # Minimal managed components
```

### Key Design Decisions
1. **ESP32 only records and plays** — all intelligence in Hermes Agent backend
2. **Switchable Agent backend** — change address to switch backend (Hermes, xiaozhi official, etc.)
3. **Configurable endpoints** — all URLs configurable via NVS/settings
4. **Two modes**: 
   - REST mode (record → transcribe → chat → TTS → play) — simpler, higher latency
   - Realtime mode (OpenAI Realtime API WebSocket) — optional, lower latency
5. **Keep xiaozhi's board/display/LED/audio codec infrastructure** — it's excellent
6. Replace protocol + app orchestration — remove xiaozhi server dependency, connect to Hermes Agent

---

## Summary

**Reuse (70%+ of code)**:
- Audio codec abstraction + all codec drivers
- Board abstraction + WiFi board + all board configs (pin definitions)
- Display system (LVGL-based LCD/OLED)
- LED system
- Button, backlight, knob, battery monitor
- Settings (NVS wrapper)
- Device state machine
- OGG demuxer
- MCP server (optional)

**Rewrite (30%)**:
- Protocol layer -> Hermes Agent WebSocket client
- Application orchestration → remove server-specific logic
- OTA → remove activation system
- Audio pipeline -> simplify to send to Agent backend

**Biggest challenge**: ESP-SR wake word is proprietary. For a fully open-source project, consider button-triggered or use the public WakeNet models that don't require NDA.
