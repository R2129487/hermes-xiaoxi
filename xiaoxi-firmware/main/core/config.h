#pragma once
#include <cstdint>
#include <cstring>

// 设备形态枚举
enum class DeviceForm : uint8_t {
    DESKTOP,     // 桌面型（无运动，听觉+视觉）
    WHEELED,     // 轮式底盘（轮子+云台摄像头）
    BIPEDAL,     // 两足行走（腿+头+手臂）
    CUSTOM,      // 自定义
};

// 单个模型端点配置
struct ModelEndpoint {
    char url[128] = "";       // API 地址，如 http://192.168.1.11:1234/v1
    char api_key[64] = "";    // API Key（空=不需要认证）
    char model[64] = "";      // 模型名，如 whisper / default / edge-tts

    bool IsEmpty() const { return url[0] == '\0'; }
};

struct XiaoXiConfig {
    // === 模型端点（3个，可填同一地址也可分开）===
    ModelEndpoint chat;         // 大语言模型（对话）
    ModelEndpoint asr;          // 语音识别（Whisper）
    ModelEndpoint tts;          // 语音合成（Edge TTS / 自建）
    ModelEndpoint vision;       // 视觉模型（RoboBrain）— 阶段二

    // 快捷字段：首次配网时用的默认 Agent 地址
    // 保持向后兼容，chat/asr/tts 为空时 fallback 到这里
    char agent_url[128] = "http://192.168.1.11:8080/v1";
    char agent_api_key[64] = "";
    char model_name[64] = "default";

    // === WiFi ===
    char wifi_ssid[64] = "CMCC-F5GG";
    char wifi_password[64] = "6f754ab3";
    bool keep_ap_on_sta = true;   // WiFi 连上后是否保留 AP 热点（true=APSTA 双模式）

    // === 设备信息 ===
    char device_name[32] = "小希";
    uint8_t volume = 80;
    bool wake_word_enabled = true;
    DeviceForm form = DeviceForm::DESKTOP;

    // === 模块开关 ===
    bool vision_enabled = false;   // 阶段二：视觉
    bool motion_enabled = false;   // 阶段三：运动

    // === 视觉配置 ===
    int camera_width = 640;
    int camera_height = 480;
    int camera_quality = 80;
    int observe_interval = 5;      // 连续观察间隔（秒）
    char vision_model[64] = "RoboBrain";  // VLM 模型名

    // === 运动配置 ===
    int servo_count = 0;           // 舵机数量
    int motor_count = 0;           // 电机数量
    uint8_t max_speed = 80;        // 最大速度（0-100）
    float obstacle_distance = 20;  // 避障距离（cm）
    bool imu_enabled = false;
    bool obstacle_enabled = false;

    // === 音频硬件 ===
    int codec_type = 0;            // 0=Dummy（先测WiFi）, 1=NoAudioCodec Simplex
    int i2s_bclk_pin = 14;         // 喇叭 BCLK
    int i2s_ws_pin = 27;           // 喇叭 LRCK
    int i2s_dout_pin = 33;         // 喇叭 DIN
    int i2s_din_pin = -1;          // (不用，Simplex 模式用独立的麦克风引脚)
    int i2s_mic_sck_pin = -1;      // 先禁用麦克风
    int i2s_mic_ws_pin = -1;       // 先禁用麦克风
    int i2s_mic_din_pin = -1;      // 先禁用麦克风

    // === 雷达 ===
    int radar_type = 0;            // 0=无, 1=超声波, 2=毫米波, 3=激光
    int radar_trig_pin = -1;
    int radar_echo_pin = -1;

    // === 获取实际使用的端点（优先用独立配置，fallback 到通用）===
    const ModelEndpoint &GetChatEndpoint() const {
        return chat.IsEmpty() ? *(const ModelEndpoint *)&agent_url : chat;
        // 注意：如果 chat 为空，fallback 用 agent_url 构造临时端点
        // 实际使用时应通过 GetEffectiveChatUrl() 等方法
    }
};

class Config {
public:
    static Config &GetInstance();

    void Init();
    const XiaoXiConfig &Get() const { return cfg_; }
    void Set(const XiaoXiConfig &cfg) { cfg_ = cfg; }
    void Save();
    void Load();

    // 便捷方法：获取实际 URL（独立配置优先，否则 fallback 通用）
    const char *GetChatUrl() const;
    const char *GetAsrUrl() const;
    const char *GetTtsUrl() const;
    const char *GetVisionUrl() const;

private:
    Config() = default;
    XiaoXiConfig cfg_;
};
