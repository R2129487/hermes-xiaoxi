#pragma once
#include <cstdint>
#include <cstddef>
#include <functional>
#include <vector>

// === 模块 3：运动 (Motion) ===
// 阶段三：舵机（腿/头/手臂）+ 电机（底盘）+ 避障
//
// 舵机通过 I2C 或 PWM 控制，支持：
//   - 两足行走（6-8 个舵机，步态规划）
//   - 轮式底盘（2-4 个直流电机，差速转向）
//   - 头部云台（2 个舵机，pan/tilt）
//
// ESP32 资源：
//   - MCPWM → 电机 PWM
//   - LEDC → 舵机 PWM（50Hz，500-2500μs）
//   - PCNT → 编码器读数（可选）
//   - ADC → 超声波/红外测距

struct MotionConfig {
    int servo_count = 0;       // 舵机数量
    int motor_count = 0;       // 电机数量
    bool imu_enabled = false;  // MPU6050
    bool obstacle_enabled = false;  // 超声波/红外
    uint16_t servo_min_us = 500;   // 舵机最小脉宽
    uint16_t servo_max_us = 2500;  // 舵机最大脉宽
};

enum class ActionType : uint8_t {
    SERVO_SET,      // 单舵机角度
    SERVO_BATCH,    // 多舵机同时
    MOTOR_MOVE,     // 底盘前进/后退
    MOTOR_TURN,     // 底盘转弯
    STOP,           // 停止
    WAIT,           // 等待
    WALK_FORWARD,   // 前进（两足）
    WALK_BACKWARD,  // 后退（两足）
    TURN_LEFT,      // 左转
    TURN_RIGHT,     // 右转
    NOD,            // 点头
    SHAKE_HEAD,     // 摇头
    WAVE_HAND,      // 挥手
    CUSTOM,         // 自定义动作序列
};

// 动作指令（从 Agent 返回，JSON 格式）
struct MotionAction {
    ActionType type;
    union {
        struct { uint8_t id; uint16_t angle; uint8_t speed; } servo;
        struct { int8_t direction; uint8_t speed; } motor;  // -1后退 0停 1前进
        struct { int16_t angle; uint8_t speed; } turn;
        struct { uint32_t ms; } wait;
    } params;
    uint32_t duration_ms = 0;
};

// 动作序列（预定义动作）
struct MotionSequence {
    const char *name;
    const MotionAction *actions;
    int count;
};

using MotionDoneCallback = std::function<void(bool success)>;

class MotionController {
public:
    static MotionController &GetInstance();

    void Init(const MotionConfig &config);
    bool IsAvailable() const { return available_; }

    // === 舵机控制 ===
    void ServoSet(uint8_t id, uint16_t angle, uint8_t speed = 50);
    void ServoBatch(const MotionAction *actions, int count);
    void ServoDisable(uint8_t id);   // 省电，释放扭矩
    void ServoDisableAll();

    // === 电机控制（轮式底盘）===
    void Move(int8_t direction, uint8_t speed);  // -1后退 0停 1前进
    void Turn(int16_t angle, uint8_t speed);     // 角度转弯
    void Stop();
    void EmergencyStop();  // 立即停止所有

    // === 高级动作（预定义）===
    void WalkForward(uint8_t speed = 50);
    void WalkBackward(uint8_t speed = 50);
    void TurnLeft(uint8_t speed = 50);
    void TurnRight(uint8_t speed = 50);
    void Nod();          // 点头
    void ShakeHead();    // 摇头
    void WaveHand();     // 挥手

    // === 动作序列执行 ===
    void ExecuteSequence(const MotionAction *actions, int count, MotionDoneCallback cb = nullptr);
    void ParseAndExecute(const char *json_actions);  // JSON → 动作序列

    // === 传感器 ===
    float GetDistance();            // 超声波距离 (cm)，-1 表示无数据
    void GetIMU(float *accel, float *gyro);  // 加速度 + 陀螺仪
    bool IsObstacleDetected();      // 避障检测

    // === 安全 ===
    void SetMaxSpeed(uint8_t max_speed) { max_speed_ = max_speed; }
    void SetObstacleDistance(float min_cm) { obstacle_min_cm_ = min_cm; }

private:
    MotionController() = default;
    bool available_ = false;

    // 舵机 PWM 控制（LEDC）
    void servo_pwm_init(uint8_t id, int gpio);
    void servo_pwm_set(uint8_t id, uint16_t pulse_us);
    static constexpr int SERVO_GPIO_MAP[8] = {
        13, 12, 14, 27, 26, 25, 33, 32  // 默认舵机 GPIO 映射
    };

    // 电机 PWM 控制（MCPWM 或 LEDC）
    void motor_pwm_init();
    void motor_set(int8_t left, int8_t right);

    uint8_t max_speed_ = 100;
    float obstacle_min_cm_ = 20.0f;  // 最小避障距离
};
