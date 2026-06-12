// board.h — 满足 xiaozhi-esp32 audio_codec.cc 依赖
#pragma once
#include <string>
#include <esp_log.h>

class Backlight { public: void SetBrightness(int p) {} };
class Display { public: virtual ~Display() = default; virtual void SetStatus(const char *s) {} };

class XzBoard {
public:
    static XzBoard &GetInstance() { static XzBoard b; return b; }
    const std::string &Name() const { static std::string n = "xiaoxi"; return n; }
    Backlight *GetBacklight() { return &bl_; }
    Display *GetDisplay() { return nullptr; }
    bool GetNetworkState() { return false; }
private:
    Backlight bl_;
};

// 让小智代码中的 Board 指向 XzBoard
#define Board XzBoard
