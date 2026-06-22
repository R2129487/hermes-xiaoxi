#include "application.h"
#include "voice_chain.h"
#include "audio/codecs/dummy_audio_codec.h"
#include "audio/codecs/no_audio_codec.h"
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static const char *TAG = "App";

Application &Application::GetInstance() { static Application i; return i; }

void Application::Init() {
    ESP_LOGI(TAG, "=== 小希固件初始化 ===");

    // 核心层
    EventBus::GetInstance();
    StateMachine::GetInstance().Init();
    Config::GetInstance().Init();
    session_.Init();

    // 硬件（包括 GPIO 按钮初始化）
    XiaoXiBoard::GetInstance().Init();

    // 通信
    WifiManager::GetInstance().Init();
    auto &cfg = Config::GetInstance().Get();
    if (cfg.wifi_ssid[0]) {
        WifiManager::GetInstance().Connect(cfg.wifi_ssid, cfg.wifi_password, cfg.keep_ap_on_sta);
    } else {
        WifiManager::GetInstance().StartAP("XiaoXi-Setup");
        StateMachine::GetInstance().Transition(DeviceState::CONFIG);
    }
    // Agent 端点初始化（3+1 个独立端点，支持同一地址 fallback）
    auto &agent = AgentClient::GetInstance();
    agent.Init(cfg.agent_url, cfg.agent_api_key, cfg.model_name);
    if (cfg.chat.url[0]) {
        agent.SetChatEndpoint(cfg.chat.url, cfg.chat.api_key, cfg.chat.model);
    }
    if (cfg.asr.url[0]) {
        agent.SetAsrEndpoint(cfg.asr.url, cfg.asr.api_key, cfg.asr.model);
    }
    if (cfg.tts.url[0]) {
        agent.SetTtsEndpoint(cfg.tts.url, cfg.tts.api_key, cfg.tts.model);
    }
    if (cfg.vision.url[0]) {
        agent.SetVisionEndpoint(cfg.vision.url, cfg.vision.api_key, cfg.vision.model);
    }

    // 输出
    LedIndicator::GetInstance().Init();
    Player::GetInstance().Init();
    Player::GetInstance().SetVolume(cfg.volume);
    XiaoXiDisplay::GetInstance().Init();

    // 音频 — 创建 Codec 并注入 AudioPipeline
    AudioConfig audio_cfg;
    audio_cfg.input_sample_rate = 16000;
    audio_cfg.output_sample_rate = 16000;

    AudioCodec *codec = nullptr;
    switch (cfg.codec_type) {
        case 0:  // Dummy（无硬件，开发测试用）
        default:
            ESP_LOGI(TAG, "Using DummyAudioCodec (no hardware)");
            codec = new DummyAudioCodec(16000, 16000);
            break;
        case 1:  // NoAudioCodec Simplex — MAX98357A + INMP441 纯 I2S 直连
            ESP_LOGI(TAG, "Using NoAudioCodecSimplex (I2S direct)");
            codec = new NoAudioCodecSimplex(
                16000, 16000,
                (gpio_num_t)cfg.i2s_bclk_pin,   // 喇叭 BCLK
                (gpio_num_t)cfg.i2s_ws_pin,      // 喇叭 LRCK
                (gpio_num_t)cfg.i2s_dout_pin,    // 喇叭 DIN
                (gpio_num_t)cfg.i2s_mic_sck_pin, // 麦克风 SCK
                (gpio_num_t)cfg.i2s_mic_ws_pin,  // 麦克风 WS
                (gpio_num_t)cfg.i2s_mic_din_pin  // 麦克风 DIN
            );
            break;
    }

    AudioPipeline::GetInstance().SetCodec(codec);
    AudioPipeline::GetInstance().Init(audio_cfg);

    // 视觉（如果启用）
    if (cfg.vision_enabled) {
        VisionConfig vision_cfg;
        vision_cfg.width = cfg.camera_width;
        vision_cfg.height = cfg.camera_height;
        vision_cfg.jpeg_quality = cfg.camera_quality;
        Camera::GetInstance().Init(vision_cfg);
    }

    // 运动（如果启用）
    if (cfg.motion_enabled) {
        MotionConfig motion_cfg;
        motion_cfg.servo_count = cfg.servo_count;
        motion_cfg.motor_count = cfg.motor_count;
        motion_cfg.imu_enabled = cfg.imu_enabled;
        motion_cfg.obstacle_enabled = cfg.obstacle_enabled;
        MotionController::GetInstance().Init(motion_cfg);
    }

    // Web 配置服务器
    WebServer::GetInstance().Init();
    WebServer::GetInstance().Start();

    ESP_LOGI(TAG, "=== 初始化完成 ===");
}

void Application::Run() {
    ESP_LOGI(TAG, "Main loop started");

    // 等待 WiFi 连接（最多 30 秒）
    auto &wifi = WifiManager::GetInstance();
    for (int i = 0; i < 30 && !wifi.IsConnected(); i++) {
        ESP_LOGI(TAG, "Waiting for WiFi... (%d/30)", i + 1);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    if (wifi.IsConnected()) {
        ESP_LOGI(TAG, "WiFi connected: %s", wifi.GetIP());
    } else {
        ESP_LOGW(TAG, "WiFi not connected, starting AP mode");
        wifi.StartAP("XiaoXi-Setup");
        StateMachine::GetInstance().Transition(DeviceState::CONFIG);
    }

    // 启动后台语音任务（唤醒词监听 + 按钮交互）
    start_voice_task();

    while (true) {
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void Application::Shutdown() {
    ESP_LOGI(TAG, "=== 小希固件关闭 ===");

    // 停止语音任务
    stop_voice_task();

    // 停止按钮检测任务
    XiaoXiBoard::GetInstance().StopButtonTask();

    // 停止 Web 服务器
    WebServer::GetInstance().Stop();

    ESP_LOGI(TAG, "Firmware shutdown complete");
}
