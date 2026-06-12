#include <cstdio>
#include <esp_log.h>
#include <nvs_flash.h>

#include "core/application.h"

static const char *TAG = "xiaoxi";

extern "C" void app_main(void)
{
    ESP_LOGI(TAG, "=== 小希固件启动 ===");

    // 初始化 NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 应用初始化 + 主循环
    Application::GetInstance().Init();
    Application::GetInstance().Run();
    Application::GetInstance().Shutdown();
}
