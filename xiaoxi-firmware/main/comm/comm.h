#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <functional>
#include <string>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

// === 模块 5：通信 (Comm) ===

// WiFi 状态
enum class WifiStatus : uint8_t {
    DISCONNECTED, CONNECTING, CONNECTED, AP_MODE,
};

using WifiStatusCallback = std::function<void(WifiStatus status)>;

// WiFi 管理
class WifiManager {
public:
    static WifiManager &GetInstance();

    void Init();
    void Connect(const char *ssid, const char *password, bool keep_ap = false);
    void StartAP(const char *ssid, const char *password = nullptr);
    void AutoConnect();
    bool IsConnected() const;
    WifiStatus GetStatus() const { return status_; }
    void OnStatus(WifiStatusCallback cb) { status_cb_ = std::move(cb); }
    const char *GetIP() const;

    // wifi_event_handler 需要写入 status_
    WifiStatus status_ = WifiStatus::DISCONNECTED;

private:
    WifiManager() = default;
    WifiStatusCallback status_cb_;
};

// Agent API 回调
using AsrResultCallback = std::function<void(const char *text)>;
using LlmTokenCallback = std::function<void(const char *token)>;
using LlmDoneCallback = std::function<void(const char *full_text)>;
using TtsAudioCallback = std::function<void(const uint8_t *data, size_t len)>;

struct AgentCallbacks {
    AsrResultCallback on_asr;
    LlmTokenCallback on_llm_token;
    LlmDoneCallback on_llm_done;
    TtsAudioCallback on_tts_audio;
};

// Agent 消息
struct AgentMessage {
    const char *role;
    const char *content;
};

// Agent API 客户端
// 支持 Chat/ASR/TTS/Vision 分别配置不同端点
class AgentClient {
public:
    static AgentClient &GetInstance();

    // 初始化（向后兼容，所有端点用同一地址）
    void Init(const char *base_url, const char *api_key, const char *model);

    // 分别配置各端点
    void SetChatEndpoint(const char *url, const char *api_key, const char *model);
    void SetAsrEndpoint(const char *url, const char *api_key, const char *model);
    void SetTtsEndpoint(const char *url, const char *api_key, const char *model);
    void SetVisionEndpoint(const char *url, const char *api_key, const char *model);

    void SetCallbacks(const AgentCallbacks &cb) { cb_ = cb; }

    // ASR: POST /v1/audio/transcriptions
    void Asr(const uint8_t *pcm_data, size_t pcm_len, int sample_rate = 16000);

    // Chat: POST /v1/chat/completions (SSE 流式)
    void Chat(const AgentMessage *messages, int count);

    // TTS: POST /v1/audio/speech
    void Tts(const char *text);

    // 视觉理解
    void VisionQuery(const uint8_t *jpeg_data, size_t jpeg_len, const char *question);

    // 运动指令
    void MotionCommand(const uint8_t *jpeg_data, size_t jpeg_len, const char *instruction);
    void MotionExecuteJson(const char *actions_json);

    // 状态
    bool IsBusy() const { return busy_; }
    void Cancel() { busy_ = false; }

private:
    AgentClient() = default;

    // 内部端点结构
    struct Endpoint {
        char url[128] = {};
        char api_key[64] = {};
        char model[64] = {};

        void Set(const char *u, const char *k, const char *m) {
            if (u) strncpy(url, u, sizeof(url) - 1);
            if (k) strncpy(api_key, k, sizeof(api_key) - 1);
            if (m) strncpy(model, m, sizeof(model) - 1);
        }

        bool IsEmpty() const { return url[0] == '\0'; }
    };

    Endpoint chat_ep_;    // 大语言模型
    Endpoint asr_ep_;     // 语音识别
    Endpoint tts_ep_;     // 语音合成
    Endpoint vision_ep_;  // 视觉模型

    // 向后兼容：Init() 设置的通用端点作为 fallback
    Endpoint default_ep_;

    AgentCallbacks cb_;
    bool busy_ = false;

    // 获取实际使用的端点
    const Endpoint &GetChatEp() const { return chat_ep_.IsEmpty() ? default_ep_ : chat_ep_; }
    const Endpoint &GetAsrEp() const { return asr_ep_.IsEmpty() ? default_ep_ : asr_ep_; }
    const Endpoint &GetTtsEp() const { return tts_ep_.IsEmpty() ? default_ep_ : tts_ep_; }
    const Endpoint &GetVisionEp() const { return vision_ep_.IsEmpty() ? default_ep_ : vision_ep_; }
};

// Web 配置服务器
class WebServer {
public:
    static WebServer &GetInstance();

    void Init();
    void Start();
    void Stop();
    void StartCaptivePortal();
    bool IsRunning() const { return running_; }

private:
    WebServer() = default;
    bool running_ = false;
    TaskHandle_t dns_task_ = nullptr;
};
