#pragma once
#include <cstdint>
#include <cstddef>
#include <functional>

enum class EventType : uint8_t {
    // 输入
    WAKE_WORD_DETECTED = 0,
    BUTTON_PRESSED,
    BUTTON_RELEASED,
    VAD_SPEECH_START,
    VAD_SPEECH_END,

    // Agent
    ASR_RESULT,
    LLM_TOKEN,
    LLM_DONE,
    TTS_AUDIO,

    // 视觉
    VISION_FRAME,
    VISION_RESULT,

    // 运动
    MOTION_DONE,
    OBSTACLE_DETECTED,

    // 系统
    WIFI_CONNECTED,
    WIFI_DISCONNECTED,
    ERROR,

    MAX
};

struct Event {
    EventType type;
    const void *data = nullptr;
    size_t data_len = 0;
};

using EventCallback = std::function<void(const Event &event)>;

class EventBus {
public:
    static EventBus &GetInstance();

    void On(EventType type, EventCallback callback);
    void Off(EventType type, EventCallback callback);
    void Emit(EventType type, const void *data = nullptr, size_t data_len = 0);

private:
    EventBus() = default;
    static constexpr int MAX_LISTENERS = 16;
    EventCallback listeners_[static_cast<int>(EventType::MAX)][MAX_LISTENERS] = {};
    int count_[static_cast<int>(EventType::MAX)] = {};
};
