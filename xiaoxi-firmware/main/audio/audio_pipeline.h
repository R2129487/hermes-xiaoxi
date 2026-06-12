#pragma once
#include <cstdint>
#include <cstddef>
#include <vector>
#include <functional>
#include <string>

// 小智的 AudioCodec 驱动
#include "audio_codec.h"

// === 模块 1：听觉 (Audio) ===

enum class AudioFormat : uint8_t {
    PCM_16K,    // 16kHz 16bit 单声道
    PCM_24K,    // 24kHz 16bit 单声道
    OPUS,       // Opus 编码
};

struct AudioConfig {
    int input_sample_rate = 16000;
    int output_sample_rate = 24000;
    int input_channels = 1;
    int output_channels = 1;
};

// 唤醒类型
enum class WakeType : uint8_t {
    NONE = 0,
    KEYWORD,        // 语音唤醒词
    BUTTON,         // 按钮触发
};

// 音频管线（封装录音+播放+VAD）
// 注意：唤醒词检测由 VoiceChain 使用 EspWakeWord 独立实现，
// AudioPipeline 仅提供原始音频流和 VAD
class AudioPipeline {
public:
    static AudioPipeline &GetInstance();

    void Init(const AudioConfig &config);

    // 设置小智的 Codec 驱动
    void SetCodec(AudioCodec *codec);

    // 录音
    void StartRecording();
    void StopRecording();
    int Read(int16_t *buf, int samples);
    bool IsRecording() const { return recording_; }

    // 录音并收集完整一句话（VAD 检测静音自动停止）
    std::vector<int16_t> RecordUtterance(int max_seconds = 10);

    // 播放 PCM 数据
    void Play(const int16_t *data, size_t samples);

    // VAD：当前是否有声音（能量检测）
    // 返回帧能量 > threshold 则为说话中
    bool IsSpeaking();

    // 配置
    const AudioConfig &GetConfig() const { return config_; }

private:
    AudioPipeline() = default;
    AudioCodec *codec_ = nullptr;
    AudioConfig config_;
    bool recording_ = false;
};
