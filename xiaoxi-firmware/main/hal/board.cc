#include "board.h"
#include <esp_log.h>
#include <driver/gpio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static const char *TAG = "Board";

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

    // 创建按钮检测任务
    TaskHandle_t task_handle;
    xTaskCreate(button_task, "button_task", 2048, this, 5, &task_handle);
    ESP_LOGI(TAG, "Button task created");
}

void XiaoXiBoard::button_task(void *arg) {
    auto *self = static_cast<XiaoXiBoard *>(arg);
    int last_stable = 1;   // 上拉默认高电平
    int press_count = 0;   // 按下消抖计数
    bool pressed = false;  // 是否已触发按下事件

    while (true) {
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

        last_stable = state;
        vTaskDelay(pdMS_TO_TICKS(10));  // 10ms 间隔，让出 CPU
    }
}
