# XiaoXi Project (hermes-xiaoxi) · Product Lineup v3.0

> Portable AI Voice Assistant · Open Source Hardware + Open Source Firmware · 2026

---

## Core Philosophy

**ESP32 only handles audio capture and playback. The Agent backend handles all the intelligence.**

The ESP32 firmware is compiled once and never needs to be changed again — all settings are modified via the web page. Want to switch Agent backends? Just change an address. Adding new features? The backend handles it; ESP32 doesn't even know.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    ESP32 Device Side                 │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ 🎤 Mic    │  │ 🔈 Speaker│  │ 🔘 Button·LED·Screen│   │
│  └────┬─────┘  └────▲─────┘  └──────────────────┘   │
│       │              │                                │
│  ┌────▼──────────────┴────────────────────────┐      │
│  │          Audio Codec (Opus)                  │      │
│  └────┬──────────────────────────▲─────────────┘      │
│       │                          │                     │
│  ┌────▼──────────────────────────┴─────────────┐      │
│  │          WiFi Management + Network Comms      │      │
│  └────┬────────────────────────────────────────┘      │
│       │                                                │
│  ┌────▼────────────────────────────────────────┐      │
│  │          Web Config Page (AP Hotspot Mode)    │      │
│  │  · Agent Backend Address  · WiFi Config       │      │
│  │  · Volume/Language        · Device Name       │      │
│  │  · Wake Word Toggle                           │      │
│  └─────────────────────────────────────────────┘      │
└───────────────────────┬───────────────────────────────┘
                        │ WiFi / Phone Hotspot
                        │ WebSocket / HTTP
                        ↓
┌─────────────────────────────────────────────────────┐
│                  Agent Backend (Brain)                 │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ 🗣️ ASR    │  │ 🧠 LLM    │  │ 🎵 TTS           │   │
│  │ Speech Rec│  │ Model Inf │  │ Voice Synthesis  │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │            Context Management (Chat History)   │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │            Tool Calling (Function Calling / MCP)│    │
│  │  · Weather Query    · Search Engine            │    │
│  │  · Music Playback   · Smart Home               │    │
│  │  · Calendar Mgmt    · Custom Tools             │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  Supported Backends:                                  │
│  · Hermes (local computer)                            │
│  · Other compatible Agent platforms                   │
│  · Other AI Agent platforms                           │
│  · Local Ollama (fully offline)                       │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │            Web Admin Dashboard                  │    │
│  │  · Persona Prompt  · API Key  · Tool Toggle    │    │
│  │  · TTS Voice Select · Chat History Viewer      │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## ESP32 Device Side — Detailed Design

### Firmware Features (Compile Once, Use Forever)

| Module | Feature | Details |
|--------|---------|---------|
| Audio Capture | I2S Mic → Opus Encode | 16kHz mono, 60ms frames |
| Audio Playback | Opus Decode → I2S Speaker | 24kHz output |
| Wake Word | ESP-SR WakeNet | "Ni Hao XiaoXin" for Desk versions, button for Pen versions |
| WiFi Management | Auto-connect + AP Provisioning | Auto-switch between home WiFi / phone hotspot |
| Web Config | Config page in AP hotspot mode | Access via mobile browser at 192.168.4.1 |
| Button | Single/Long/Double press | Debounce, GPIO interrupt |
| LED | Status indicator | Standby/Recording/Thinking/Playing |
| Screen | OLED/LCD display | Chat text, status, time |
| OTA | Remote firmware update | Upload new firmware via web page |
| Power Saving | Light Sleep | Sleep after 30s idle, wake via button/wake word |

### Web Configuration Page (Runs on ESP32)

After connecting to the ESP32's AP hotspot, access the config page in your browser:

```
┌─────────────────────────────────┐
│         XiaoXi · Device Config   │
│                                   │
│  WiFi Settings                    │
│  ├─ WiFi Name:  [________]        │
│  ├─ WiFi Pass:  [________]        │
│  └─ [Scan Available WiFi]         │
│                                   │
│  Agent Backend Settings           │
│  ├─ Backend URL: [ws://192.168.1.11] │
│  ├─ Protocol:    [WebSocket ▼]    │
│  └─ Auth Key:    [________]       │
│                                   │
│  Audio Settings                   │
│  ├─ Volume:    [████████░░] 80%   │
│  ├─ Wake Word: [On/Off]          │
│  └─ Language:  [Chinese ▼]       │
│                                   │
│  Device Info                      │
│  ├─ Device Name: [XiaoXi-LivingRoom] │
│  ├─ Firmware:    v2.0.0          │
│  └─ [Check for Updates]          │
│                                   │
│         [Save & Reboot]           │
└─────────────────────────────────┘
```

### Connection Methods

ESP32 connects to the Agent backend via WiFi, supporting two scenarios:

**At Home:**
```
ESP32 → Home WiFi Router → LAN → Agent Backend (192.168.1.11)
```

**On the Go:**
```
ESP32 → Phone Hotspot → Internet → Agent Backend (Cloud URL)
```

ESP32 automatically scans the known WiFi list on boot. If none are found, it waits for the user to enable their phone hotspot. The user doesn't even notice.

### Communication Protocol

ESP32 and the Agent backend communicate via **WebSocket**:

```
① ESP32 → Agent: hello message (device info, audio parameters)
② Agent → ESP32: hello response (session ID, negotiated parameters)
③ ESP32 → Agent: audio data (Opus encoded, binary frame)
④ Agent → ESP32: audio data (TTS result, Opus encoded)
⑤ ESP32 → Agent: control messages (listen/abort, JSON)
```

---

## Agent Backend — Detailed Design

### What Is the Backend

The Agent backend is the **brain of the ESP32**. It receives audio from the ESP32, performs recognition → thinking → synthesis, then sends the response audio back.

The backend can be any Agent service that supports the XiaoZhi WebSocket protocol:

| Backend | Description | Use Case |
|---------|-------------|----------|
| **Hermes (XiaoXi)** | Runs on local computer, most capable | Daily use at home |
| **Compatible Agent Platform** | Any backend implementing the same protocol | Future expansion |
| **XiaoZhi Official Server** | xiaozhi.me | Simplest, free Qwen model |
| **Self-hosted Backend** | Docker-deployed xiaozhi-server | Technical users |
| **Other AI Agent** | Any backend implementing the same protocol | Extensibility |

### Hermes Backend (XiaoXi)

Hermes runs on a local computer and is the most capable backend:

```
ESP32 → WebSocket → Hermes
                      ├── ASR (Whisper / Local Speech Recognition)
                      ├── Context Management (Multi-turn Chat Memory)
                      ├── LLM (DeepSeek / Qwen / Claude / Local Models)
                      ├── TTS (Edge TTS / GPT-SoVITS)
                      ├── Tool Calling
                      │   ├── Weather Query
                      │   ├── Search Engine
                      │   ├── Smart Home Control
                      │   ├── Calendar Management
                      │   └── MCP Custom Tools
                      └── Web Admin Dashboard
```

### Switching Backends

Just change one address on the ESP32's web config page:

```
Want to connect to Hermes?    → Enter ws://192.168.1.11:8000/xiaozhi/v1/

Want to connect to Official?  → Enter ws://api.tenclass.net/xiaozhi/v1/
```

**No firmware changes needed, no recompilation — just change the address and you're done.**

---

## Product Lineup (Four Versions)

### Product Overview

| | Pen Basic | Pen Eye | Desk Standard | Desk Eye |
|---|---|---|---|---|
| **Codename** | XiaoXi Pen | XiaoXi Pen Eye | XiaoXi Desk | XiaoXi Desk Eye |
| **Form Factor** | Normal pen/signature pen | Thick pen/marker/pointer | Desktop ornament | Desktop ornament |
| **Chip** | ESP32-C3 | ESP32-CAM (S3) | ESP32-S3 | ESP32-S3 Mini |
| **Wake Method** | Button | Button | Voice + Button | Voice + Button |
| **Camera** | ❌ | ✅ OV2640 | ❌ | ✅ OV2640 |
| **Screen** | ❌ | ❌ | ✅ OLED | ✅ OLED |
| **Web Config** | ✅ AP Hotspot | ✅ AP Hotspot | ✅ AP Hotspot | ✅ AP Hotspot |
| **Hardware Cost** | ~¥29 | ~¥55 | ~¥55 | ~¥63 |
| **Suggested Price** | ¥99-149 | ¥199-299 | ¥199-249 | ¥249-349 |

### Version 1: Pen Basic (XiaoXi Pen)

**Simplest, cheapest — pocket and go.**

| Component | Model | Price |
|-----------|-------|-------|
| MCU | ESP32-C3-ZERO/Mini (5×5mm) | ~¥6 |
| Microphone | INMP441 Digital MEMS Mic | ~¥3 |
| Amp + Speaker | MAX98357A + Micro Speaker | ~¥5 |
| Button | Tact switch (pen tail) | ~¥0.5 |
| Battery | LiPo 150mAh | ~¥3 |
| Charging | TP4056 + USB-C | ~¥1.5 |
| PCB | Custom Flex Board | ~¥2 |
| Assembly + Packaging | | ~¥8 |
| **Total** | | **~¥29** |

- Hold pen tail to talk, release to send
- LED status indicator (blue=standby, green=recording, red=thinking, blinking=playing)
- BLE Bluetooth or AP hotspot provisioning
- Power saving: sleep after 30 seconds idle

### Version 2: Pen Eye (XiaoXi Pen Eye)

**Snap a photo and ask XiaoXi — thick pen form factor.**

| Component | Model | Price |
|-----------|-------|-------|
| MCU + Camera | ESP32-CAM (S3+OV2640 integrated) | ~¥18 |
| Microphone | INMP441 Digital MEMS Mic | ~¥3 |
| Amp + Speaker | MAX98357A + Micro Speaker | ~¥5 |
| Buttons ×2 | Chat button + Photo button | ~¥1 |
| Battery | LiPo 300mAh | ~¥5 |
| Charging | TP4056 + USB-C | ~¥1.5 |
| PCB | Custom Small Board | ~¥3 |
| Assembly + Packaging | | ~¥13 |
| **Total** | | **~¥55** |

- Short press pen tail = Voice chat
- Long press pen tail 2s = Photo + voice description
- ESP32-CAM module (27×40mm), highly integrated camera
- Pen barrel ~15mm diameter, similar to marker/pointer

### Version 3: Desk Standard (XiaoXi Desk)

**Desktop voice assistant with screen and wake word.**

| Component | Model | Price |
|-----------|-------|-------|
| MCU | ESP32-S3-WROOM-1 (16MB) | ~¥12 |
| Microphone | INMP441 ×2 (dual-mic array) | ~¥6 |
| Amp + Speaker | MAX98357A + 3W Speaker | ~¥8 |
| Screen | 0.96" OLED SSD1306 | ~¥6 |
| LED | WS2812 RGB ×3 | ~¥2 |
| Buttons ×2 + USB-C | | ~¥2 |
| Enclosure | 3D printed desktop ornament | ~¥6 |
| Assembly + Packaging | | ~¥13 |
| **Total** | | **~¥55** |

- Voice wake "Ni Hao XiaoXin" + button
- OLED displays chat text, status, time
- Dual microphone AEC echo cancellation — listen while playing
- USB-C powered, no battery needed
- Can serve as Home Assistant voice terminal

### Version 4: Desk Eye (XiaoXi Desk Eye)

**Full-featured — voice + vision + screen.**

| Component | Model | Price |
|-----------|-------|-------|
| MCU | ESP32-S3 Mini (13×20mm) | ~¥14 |
| Microphone | INMP441 ×2 | ~¥6 |
| Amp + Speaker | MAX98357A + 3W Speaker | ~¥8 |
| Camera | OV2640 (2MP) | ~¥8 |
| Screen | 0.96" OLED | ~¥6 |
| LED + Buttons | | ~¥3 |
| Enclosure | 3D printed | ~¥5 |
| Assembly + Packaging | | ~¥13 |
| **Total** | | **~¥63** |

- All Desk Standard features + OV2640 camera
- Uses S3 Mini module for more compact enclosure
- Photo analysis with multimodal LLM (GPT-4o-mini / Qwen-VL)
- Voice + vision dual-channel interaction

---

## Key Differences from XiaoZhi

| | XiaoZhi (Original) | XiaoXi (Our Approach) |
|---|---|---|
| **Backend** | Hardcoded to official server | Configurable address, easily swappable |
| **Changing Settings** | Recompile firmware | Edit via web page, instant effect |
| **Agent Capabilities** | Depends on backend | Connect Hermes = Full-featured Agent |
| **Switching Models** | Modify firmware + reflash | Backend change, ESP32 doesn't know |
| **Adding Tools** | Modify firmware + reflash | Backend adds, ESP32 doesn't know |
| **Offline Use** | Requires self-hosted server | Just run Hermes on your computer |
| **WiFi Provisioning** | Requires computer client | ESP32 has built-in web page |

**In one sentence: XiaoZhi treats ESP32 as the protagonist. We treat ESP32 as a dumb terminal.**

---

## Data Flow (One Complete Conversation)

```
① User presses button (or says "Ni Hao XiaoXin")
      ↓
② ESP32 starts recording, LED turns green
      ↓
③ User finishes speaking, releases button (or VAD detects silence)
      ↓
④ ESP32 sends Opus audio to Agent backend via WebSocket
      ↓
⑤ Agent backend:
   a. ASR recognition: audio → text
   b. Context management: prepend previous conversation turns
   c. LLM inference: generate response text (streaming)
   d. Tool calling: if weather/search/etc. is needed
   e. TTS synthesis: text → audio
      ↓
⑥ Agent backend sends Opus audio back to ESP32 via WebSocket
      ↓
⑦ ESP32 decodes audio, plays through speaker, LED turns blue
      ↓
⑧ If screen version: simultaneously displays chat text
```

---

## Market Comparison

| Product | Form Factor | Price | Open Source | Swappable Backend | Portable |
|---------|-------------|-------|-------------|-------------------|----------|
| **XiaoXi Pen** | Pen | ¥99 | ✅ | ✅ | ✅ |
| Humane AI Pin | Lapel Pin | $699 | ❌ | ❌ | ✅ |
| Friend Pendant | Pendant | $99 | ❌ | ❌ | ✅ |
| Rabbit R1 | Square Block | $199 | ❌ | ❌ | ⚠️ |
| XiaoZhi AI | Desktop Ornament | ¥89-149 | ✅ | ⚠️ | ❌ |

**XiaoXi's Core Advantages:**
1. **Cheapest** — Hardware cost in the ¥30 range
2. **Most Portable** — Pen form factor, pocket and go
3. **Fully Open Source** — Firmware + Hardware + Documentation
4. **Swappable Backend** — Just change an address
5. **No Vendor Lock-in** — Any LLM/TTS/ASR
6. **No Monthly Fees** — Use your own API keys
7. **Agent Capabilities** — Connect Hermes for tool calling, smart home, context memory

---

## Next Steps

- [ ] Confirm which version to prioritize
- [ ] Design ESP32 firmware web config page
- [ ] Implement ESP32 ↔ Agent backend WebSocket protocol
- [ ] Draw hardware schematic
- [ ] Design pen version PCB and enclosure
- [ ] Prepare project documentation for GitHub

---

*XiaoXi Project (hermes-xiaoxi) · Cao Ge & XiaoXi Team · June 2026*