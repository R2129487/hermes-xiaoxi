#include <cstdio>
#include <esp_log.h>
#include <esp_err.h>
#include <nvs_flash.h>

#include "core/application.h"

static const char *TAG = "xiaoxi";

extern "C" void app_main(void)
{
    ESP_LOGI(TAG, "=== 小希固件启动 ===");

    // NVS 初始化委托给 Config::Init()，避免重复初始化
    // 注意：main.cc 中不再直接调用 nvs_flash_init()
    // Config::Init() 内部会处理 NVS 初始化和擦除/恢复逻辑

    // 应用初始化 + 主循环
    Application::GetInstance().Init();
    Application::GetInstance().Run();
    Application::GetInstance().Shutdown();

    ESP_LOGI(TAG, "=== 小希固件退出 ===");
}
