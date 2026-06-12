#pragma once
#include <cstdint>
#include <cstddef>
#include <string>

// === 模块 4：输出 (Output) ===

enum class PlayFormat : uint8_t { PCM, OPUS };

enum class LedState : uint8_t {
    OFF, IDLE, LISTENING, THINKING, SPEAKING,
    ERROR, CAPTURING, MOVING,
};

enum class DisplayEmotion : uint8_t {
    IDLE, LISTENING, THINKING, SPEAKING, HAPPY, SAD, ERROR,
};

// 音频播放器
class Player {
public:
    static Player &GetInstance();

    void Init();
    void SetVolume(uint8_t volume);
    void Play(const uint8_t *data, size_t len, PlayFormat format);
    bool IsPlaying() const { return playing_; }
    void Stop();

    // 流式播放
    void StreamStart(PlayFormat format);
    void StreamWrite(const uint8_t *data, size_t len);
    void StreamStop();

private:
    Player() = default;
    bool playing_ = false;
    uint8_t volume_ = 80;
};

// LED 状态指示
class LedIndicator {
public:
    static LedIndicator &GetInstance();

    void Init();
    void SetState(LedState state);
    void SetRGB(uint8_t r, uint8_t g, uint8_t b);
    void SetBrightness(uint8_t brightness);

private:
    LedIndicator() = default;
};

// 显示（LCD/OLED）
class XiaoXiDisplay {
public:
    static XiaoXiDisplay &GetInstance();

    void Init();
    bool IsAvailable() const { return available_; }
    void ShowText(const char *text);
    void ShowEmotion(DisplayEmotion emotion);
    void ShowStatus(const char *status);
    void Clear();

private:
    XiaoXiDisplay() = default;
    bool available_ = false;
};
