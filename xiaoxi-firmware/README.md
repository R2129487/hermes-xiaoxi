# 小希固件 (hermes-xiaoxi)

ESP32 AI 语音助手固件 — 模块化架构

## 模块

| 模块 | 目录 | 职责 |
|------|------|------|
| Core | main/core/ | 应用调度、状态机、事件总线、配置 |
| Audio | main/audio/ | 录音、唤醒词、VAD、音频处理 |
| Vision | main/vision/ | 摄像头、图像采集、视频流 |
| Motion | main/motion/ | 舵机、电机、IMU、避障 |
| Output | main/output/ | 音频播放、LED、显示 |
| Comm | main/comm/ | WiFi、Agent API、Web 配置 |
| HAL | main/hal/ | 硬件抽象层、板子配置 |

## 编译

```bash
source ~/esp/esp-idf/export.sh
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyACM0 flash
```

## 配置

首次烧录后：
1. ESP32 自动开启 AP 热点 "XiaoXi-XXXX"
2. 手机连接热点，浏览器访问 192.168.4.1
3. 配置 WiFi、Agent 后端地址、API Key
4. 保存重启

## Agent 后端

支持任何 OpenAI 兼容 API：
- LM Studio (本地)：http://192.168.1.11:1234/v1
- DeepSeek API：https://api.deepseek.com/v1
- Hermes Agent：http://127.0.0.1:8642/v1

## 许可证

MIT — 音频驱动部分参考 xiaozhi-esp32 (MIT)
