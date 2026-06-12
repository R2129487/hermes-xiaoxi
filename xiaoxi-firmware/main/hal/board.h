#pragma once
#include <cstdint>
#include <functional>

// 按钮事件回调
using ButtonCallback = std::function<void()>;

class XiaoXiBoard {
public:
    static XiaoXiBoard &GetInstance();

    void Init();

    // 板卡信息
    const char *GetName() const { return name_; }
    bool HasCamera() const { return has_camera_; }
    bool HasDisplay() const { return has_display_; }
    bool HasSpeaker() const { return has_speaker_; }
    bool HasMicrophone() const { return has_microphone_; }

    // GPIO 按钮
    void RegisterButtonCallback(ButtonCallback cb);

    // 获取唤醒词模型路径（用于 ESP-SR esp_srmodel_init）
    // 返回 "model" 或具体分区路径
    const char *GetWakeWordModelPath() const { return "model"; }

private:
    XiaoXiBoard() = default;

    // 按钮任务（FreeRTOS 任务检测 GPIO 电平）
    static void button_task(void *arg);

    const char *name_ = "xiaoxi-generic";
    bool has_camera_ = false;
    bool has_display_ = false;
    bool has_speaker_ = true;
    bool has_microphone_ = true;

    ButtonCallback button_cb_ = nullptr;

    // 按钮 GPIO 引脚（默认 GPIO0 = BOOT 按钮，可配置）
    static constexpr int BUTTON_GPIO = 0;
};
