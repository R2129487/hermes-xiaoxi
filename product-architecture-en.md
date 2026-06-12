# 🖊️ XiaoXi (hermes-xiaoxi) · Product Architecture v3.0

> ESP32 Device + Agent Backend · Compile firmware once · Change Agent by editing address · 2026

---

## 🏗️ Core Architecture: ESP32 Device + Agent Backend

```mermaid
graph LR
    subgraph ESP32["🎤 ESP32 Device<br/>Compile once · Long-term use · All settings via Web page"]
        MIC["🎤 Microphone<br/>I2S · INMP441 · 16kHz PCM"]
        SPK["🔈 Speaker<br/>I2S · MAX98357 · Opus decode"]
        TRIGGER["🔔 Trigger<br/>Pen: hold button to talk<br/>Desk: wake word + button"]
        CODEC["🔊 Audio Codec<br/>Opus encode ↑ + decode ↓ · VAD · AEC (desk)"]
        WIFI["📶 WiFi Manager<br/>Auto-connect home WiFi<br/>Fallback: phone hotspot"]
        WS["📡 WebSocket<br/>Connect to Agent backend<br/>Opus audio + JSON control"]
        WEB["⚙️ Web Config Page<br/>Phone → AP hotspot → 192.168.4.1<br/>· Agent URL · WiFi · Volume · Language · OTA"]
        HW["🔘 Button · LED<br/>Single/long/double click · Status LED"]
        SCREEN["🖥️ Screen (Desk)<br/>OLED · Chat text · Status · Clock"]
        CAM["📷 Camera OV2640 (Eye)<br/>JPEG → send to Agent for multimodal analysis"]
        OTA["🔄 OTA firmware upgrade · Upload via Web page · No USB needed"]
        PEN_PWR["🔋 Pen: LiPo + USB-C"]
        DESK_PWR["🔌 Desk: USB-C constant power"]
    end

    subgraph Network["📶 Network Layer<br/>WiFi / Phone Hotspot<br/>WebSocket / HTTP<br/>Home → LAN · Out → Internet"]
    end

    subgraph Agent["🧠 Agent Backend (Brain)<br/>All intelligence lives here · Can be Hermes, XiaoZhi, custom, any compatible Agent"]
        ASR["🗣️ ASR Speech Recognition<br/>Whisper · DeepSeek · Paraformer<br/>Opus audio → text"]
        LLM["🧠 LLM Reasoning<br/>DeepSeek · Qwen · Claude · GPT<br/>Gemini · Local Ollama<br/>Text → streamed response"]
        TTS["🎵 TTS Speech Synthesis<br/>OpenAI TTS · Edge TTS · GPT-SoVITS<br/>Text → Opus audio"]
        CTX["📋 Context Manager<br/>Multi-turn history · Persona prompt · Memory"]
        VISION["👁️ Vision Understanding<br/>GPT-4o-mini · QwenVL (for Eye versions)"]
        TOOLS["🛠️ Tool Calling (Function Calling / MCP)<br/>🌤️ Weather · 🔍 Search · 🎵 Music · 🏠 Smart Home<br/>📅 Calendar · 📧 Email · 💡 Home Assistant · 🔧 Custom MCP · 📱 Mi/Tuya"]
        BACKENDS["🔄 Available Backends<br/>Hermes (local PC) · Other compatible Agents · Any protocol-compatible backend<br/>⚡ ESP32 only cares about the address · Switch backend = change address, no firmware change"]
        ADMIN["🌐 Agent Admin Panel<br/>Persona prompt · API Key · Tool toggle · TTS voice · Chat history · Device management"]
        FLOW["📡 Data Flow: Complete Conversation<br/>① Press button / wake → ② ESP32 records (Opus) → ③ Send to Agent<br/>④ ASR → LLM → TTS → ⑤ Agent returns Opus → ⑥ ESP32 decodes & plays → ⑦ Screen shows text"]
    end

    MIC --> CODEC
    TRIGGER --> CODEC
    CODEC --> WS
    WS --> Network
    Network -->|Audio ↑| Agent
    Agent -->|Reply audio ↓| Network
    Network --> WS
    ASR --> LLM --> TTS
    LLM --> CTX
    LLM --> TOOLS
```

---

## 📦 Four Product Versions

| | 🖊️ Pen Basic (C3) | 📸 Pen Eye (CAM) | 🖥️ Desk Standard (S3) | 👁️ Desk Eye (S3 Mini) |
|---|---|---|---|---|
| **Tag** | XiaoXi Pen · C3 | XiaoXi Pen Eye · CAM | XiaoXi Desk · S3 | XiaoXi Desk Eye · S3 Mini |
| **Chip** | ESP32-C3 (5×5mm) | ESP32-CAM (S3+OV2640) | ESP32-S3 | ESP32-S3 Mini (13×20mm) |
| **Trigger** | Button (hold at pen tip) | Button (short press: talk, long: snap) | "Hello XiaoXin" + button | "Hello XiaoXin" + button |
| **Web Config** | ✅ AP hotspot | ✅ AP hotspot | ✅ AP hotspot | ✅ AP hotspot |
| **Price** | ¥99 ~ ¥149 | ¥199 ~ ¥299 | ¥199 ~ ¥249 | ¥249 ~ ¥349 |
| **HW Cost** | ~¥29 | ~¥55 | ~¥55 | ~¥63 |
| **Voice Chat** | ✅ | ✅ | ✅ | ✅ |
| **Photo/Vision** | ❌ | ✅ Snap & understand | ❌ | ✅ |
| **Screen** | ❌ | ❌ | ✅ OLED display | ✅ |
| **Wake Word** | ❌ | ❌ | ✅ + interrupt | ✅ |
| **AEC Echo Cancel** | ❌ | ❌ | ✅ | ✅ |
| **Camera** | ❌ | ✅ OV2640 | ❌ | ✅ |
| **Multimodal LLM** | ❌ | ✅ | ❌ | ✅ |
| **Home Assistant** | ❌ | ❌ | ✅ | ✅ |
| **Hotspot WiFi** | ✅ | ✅ | ✅ | ✅ |

---

## ⚡ Core Differences: XiaoZhi vs XiaoXi

| Comparison | XiaoZhi (Original) | XiaoXi (Our Solution) |
|---|---|---|
| Backend Connection | Hardcoded to official server | **Configurable address, switch freely** |
| Change Settings | Recompile firmware + reflash | **Web page edit, instant effect** |
| Switch LLM | Modify firmware | **Backend swap, ESP32 unaware** |
| Add Tools | Modify firmware | **Backend adds, ESP32 unaware** |
| Agent Capability | Depends on backend | **Connect Hermes = full Agent** |
| Offline Use | Requires Docker self-hosted server | **Just run Hermes on PC** |
| Network Setup | Requires PC client | **ESP32 built-in Web page** |
| Hardware Cost | ~¥50 | **From ~¥29** |

---

<div align="center">

🖊️ **XiaoXi** hermes-xiaoxi · ESP32 Device + Agent Backend · Open Source Hardware + Firmware · MIT License · 2026

</div>
