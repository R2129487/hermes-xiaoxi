#include "radar.h"
#include <esp_log.h>
#include <cstring>

static const char *TAG = "Radar";

RadarSensor &RadarSensor::GetInstance() {
    static RadarSensor instance;
    return instance;
}

void RadarSensor::Init(const RadarConfig &config) {
    type_ = config.type;

    switch (type_) {
        case RadarType::NONE:
            ESP_LOGI(TAG, "Radar disabled");
            available_ = false;
            return;

        case RadarType::ULTRASONIC:
            // TODO: HC-SR04 GPIO 初始化
            // gpio_config trig_pin 输出, echo_pin 输入
            ESP_LOGI(TAG, "Ultrasonic init: trig=%d echo=%d",
                     config.trig_pin, config.echo_pin);
            available_ = (config.trig_pin >= 0 && config.echo_pin >= 0);
            break;

        case RadarType::MMWAVE:
            // TODO: LD2410 UART 初始化
            // uart_driver_install(config.uart_baud)
            ESP_LOGI(TAG, "mmWave init: tx=%d rx=%d baud=%d",
                     config.uart_tx_pin, config.uart_rx_pin, config.uart_baud);
            available_ = (config.uart_tx_pin >= 0 && config.uart_rx_pin >= 0);
            break;

        case RadarType::LIDAR:
            // TODO: RPLIDAR UART 初始化
            ESP_LOGI(TAG, "LiDAR init: tx=%d rx=%d baud=%d",
                     config.uart_tx_pin, config.uart_rx_pin, config.uart_baud);
            available_ = (config.uart_tx_pin >= 0 && config.uart_rx_pin >= 0);
            break;
    }

    if (available_) {
        ESP_LOGI(TAG, "Radar ready: type=%d", (int)type_);
    }
}

float RadarSensor::GetDistance() {
    if (!available_) return -1.0f;

    switch (type_) {
        case RadarType::ULTRASONIC:
            // TODO: HC-SR04 测距
            // trig 10us 脉冲 → echo 高电平时间 → 距离
            // distance = echo_time_us * 0.034 / 2
            return -1.0f;

        case RadarType::MMWAVE:
            // TODO: LD2410 UART 读取最近目标距离
            return -1.0f;

        default:
            return -1.0f;
    }
}

bool RadarSensor::DetectTarget(RadarTarget &target) {
    if (!available_ || type_ != RadarType::MMWAVE) return false;
    // TODO: LD2410 解析目标数据帧
    // 返回：距离、速度、运动状态、人体识别
    return false;
}

void RadarSensor::StartScan(RadarCallback cb) {
    if (!available_ || type_ != RadarType::LIDAR) return;
    scan_cb_ = cb;
    // TODO: RPLIDAR 扫描任务
    ESP_LOGI(TAG, "LiDAR scan started");
}

void RadarSensor::StopScan() {
    scan_cb_ = nullptr;
}

void RadarSensor::StartMonitor(TargetCallback cb) {
    if (!available_ || type_ != RadarType::MMWAVE) return;
    target_cb_ = cb;
    // TODO: LD2410 持续监听任务
    ESP_LOGI(TAG, "mmWave monitor started");
}

void RadarSensor::StopMonitor() {
    target_cb_ = nullptr;
}

bool RadarSensor::IsObstacle(float min_distance_cm) {
    return GetClosestDistance() > 0 && GetClosestDistance() < min_distance_cm;
}

float RadarSensor::GetClosestDistance() {
    return GetDistance();
}
