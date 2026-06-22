#include "board.h"
#include <esp_log.h>
#include <driver/gpio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <atomic>

static const char *TAG = "Board";

static std::atomic<bool> s_button_task_running{false};
static TaskHandle_t s_button_task_handle = nullptr;

XiaoXiBoard &XiaoXiBoard::GetInstance() {
    static XiaoXiBoard i;
    return i;
}

void XiaoXiBoard::Init() {
    ESP_LOGI(TAG, "Board init: %s", name_);

    // 配置按钮 GPIO（上拉输入）
    gpio_config_t io_conf = {};
    io_conf.pin_bit_mask = (1ULL << BUTTON_GPIO);
    io_conf.mode = GPIO_MODE_INPUT;
    io_conf.pull_up_en = GPIO_PULLUP_ENABLE;
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&io_conf);

    ESP_LOGI(TAG, "Button GPIO%d configured (pull-up, active low)", BUTTON_GPIO);
}

void XiaoXiBoard::RegisterButtonCallback(ButtonCallback cb) {
    button_cb_ = cb;

    if (s_button_task_running.load()) {
        ESP_LOGW(TAG, "Button task already running, stopping first...");
        s_button_task_running.store(false);
        vTaskDelay(pdMS_TO_TICKS(50));
    }

    // 创建按钮检测任务
    s_button_task_running.store(true);
    BaseType_t ret = xTaskCreate(button_task, "button_task", 2048, this, 5, &s_button_task_handle);
    if (ret != pdTRUE) {
        ESP_LOGE(TAG, "Failed to create button task");
        s_button_task_running.store(false);
        return;
    }
    ESP_LOGI(TAG, "Button task created");
}

void XiaoXiBoard::StopButtonTask() {
    s_button_task_running.store(false);
    if (s_button_task_handle) {
        vTaskDelay(pdMS_TO_TICKS(50));
        s_button_task_handle = nullptr;
    }
}

void XiaoXiBoard::button_task(void *arg) {
    auto *self = static_cast<XiaoXiBoard *>(arg);
    int press_count = 0;   // 按下消抖计数
    bool pressed = false;  // 是否已触发按下事件

    ESP_LOGI(TAG, "Button task started");

    while (s_button_task_running.load()) {
        int state = gpio_get_level((gpio_num_t)BUTTON_GPIO);

        if (state == 0) {
            // 按钮被按着（低电平）
            if (!pressed) {
                press_count++;
                if (press_count >= 5) {
                    // 消抖确认，触发按下事件
                    pressed = true;
                    ESP_LOGI(TAG, "Button pressed!");
                    if (self->button_cb_) {
                        self->button_cb_();
                    }
                }
            }
        } else {
            // 按钮松开（高电平）
            press_count = 0;
            pressed = false;
        }

        vTaskDelay(pdMS_TO_TICKS(10));  // 10ms 间隔，让出 CPU
    }

    ESP_LOGI(TAG, "Button task stopped");
    s_button_task_handle = nullptr;
    vTaskDelete(nullptr);
}
