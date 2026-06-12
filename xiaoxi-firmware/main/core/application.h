#pragma once
#include "core/event_bus.h"
#include "core/state_machine.h"
#include "core/config.h"
#include "core/session.h"
#include "audio/audio_pipeline.h"
#include "vision/camera.h"
#include "motion/actuator.h"
#include "output/output.h"
#include "comm/comm.h"
#include "hal/board.h"

class Application {
public:
    static Application &GetInstance();

    void Init();
    void Run();     // 主循环（事件驱动）
    void Shutdown();

private:
    Application() = default;
    Session session_;
};
