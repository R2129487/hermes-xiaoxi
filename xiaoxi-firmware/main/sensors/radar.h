#pragma once
#include <cstdint>
#include <cstddef>
#include <functional>

// === 雷达模块接口 ===
// 预留接口，支持多种雷达类型：
//   - 超声波 HC-SR04（GPIO触发，简单测距）
//   - 毫米波 LD2410（UART，人体检测+距离+运动状态）
//   - 激光雷达 RPLIDAR（UART，2D扫描建图）
//
// 统一抽象：所有雷达都输出"距离+角度"扫描数据

enum class RadarType : uint8_t {
    NONE = 0,
    ULTRASONIC,     // 超声波（单点测距）
    MMWAVE,         // 毫米波（人体检测）
    LIDAR,          // 激光雷达（2D扫描）
};

// 单个测距点
struct RadarPoint {
    float distance_cm;    // 距离（cm），<0 表示无效
    float angle_deg;      // 角度（度），0=正前方
    float intensity;      // 信号强度（0-1）
};

// 雷达扫描结果
struct RadarScan {
    RadarPoint *points;   // 点数组
    int count;            // 点数量
    uint32_t timestamp;   // 时间戳(ms)
};

// 目标检测结果（毫米波/激光雷达）
struct RadarTarget {
    float distance_cm;
    float angle_deg;
    float speed_cm_s;     // 接近/远离速度，正=靠近
    bool is_moving;
    bool is_human;        // 毫米波有人体识别
};

using RadarCallback = std::function<void(const RadarScan &scan)>;
using TargetCallback = std::function<void(const RadarTarget &target)>;

struct RadarConfig {
    RadarType type = RadarType::NONE;
    // 超声波 GPIO
    int trig_pin = -1;
    int echo_pin = -1;
    // UART 引脚（毫米波/激光雷达）
    int uart_tx_pin = -1;
    int uart_rx_pin = -1;
    int uart_baud = 115200;
    // 扫描频率
    int scan_hz = 10;
};

class RadarSensor {
public:
    static RadarSensor &GetInstance();

    void Init(const RadarConfig &config);
    bool IsAvailable() const { return available_; }
    RadarType GetType() const { return type_; }

    // === 单次测距（超声波/毫米波）===
    float GetDistance();  // 返回最近目标距离(cm)，<0=无数据

    // === 目标检测（毫米波）===
    bool DetectTarget(RadarTarget &target);

    // === 扫描模式（激光雷达）===
    void StartScan(RadarCallback cb);
    void StopScan();

    // === 持续监听（毫米波人体检测）===
    void StartMonitor(TargetCallback cb);
    void StopMonitor();

    // === 避障辅助 ===
    bool IsObstacle(float min_distance_cm = 20.0f);
    float GetClosestDistance();  // 返回最近障碍物距离

private:
    RadarSensor() = default;
    RadarType type_ = RadarType::NONE;
    bool available_ = false;
    RadarCallback scan_cb_;
    TargetCallback target_cb_;
};
