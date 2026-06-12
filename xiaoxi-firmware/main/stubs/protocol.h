// protocol.h — 满足 xiaozhi-esp32 audio_service.h 依赖
// 小智的协议抽象，我们不用
#pragma once
#include <cstddef>
#include <string>
#include <functional>

enum class DeviceState { IDLE, CONNECTING, LISTENING, SPEAKING, UPDATING };

class Protocol {
public:
    virtual ~Protocol() = default;
    virtual void SendAudio(const std::string &data) {}
    virtual void SendWakeWord() {}
    virtual void SendText(const std::string &text) {}
    virtual bool IsAudioChannelOpened() { return false; }
    virtual bool IsServerSideVad() { return false; }
    virtual bool SupportsBinaryProtocol() { return false; }
    virtual bool SupportsCompression() { return false; }
    virtual std::string GetDeviceStateJson() { return "{}"; }
    virtual void CloseAudioChannel() {}
};
