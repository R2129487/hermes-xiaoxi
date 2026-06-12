#include "actuator.h"
#include <esp_log.h>
#include <driver/ledc.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <cstring>

static const char *TAG = "Motion";

const int MotionController::SERVO_GPIO_MAP[8];

MotionController &MotionController::GetInstance() {
    static MotionController instance;
    return instance;
}

void MotionController::Init(const MotionConfig &config) {
    ESP_LOGI(TAG, "Motion init: servos=%d motors=%d imu=%s obstacle=%s",
             config.servo_count, config.motor_count,
             config.imu_enabled ? "yes" : "no",
             config.obstacle_enabled ? "yes" : "no");

    if (config.servo_count > 0) {
        // 初始化舵机 PWM
        for (int i = 0; i < config.servo_count && i < 8; i++) {
            servo_pwm_init(i, SERVO_GPIO_MAP[i]);
        }
        ESP_LOGI(TAG, "Servo PWM initialized: %d channels", config.servo_count);
    }

    if (config.motor_count > 0) {
        motor_pwm_init();
        ESP_LOGI(TAG, "Motor PWM initialized");
    }

    available_ = (config.servo_count > 0 || config.motor_count > 0);
}

// === 舵机 PWM 初始化（LEDC，50Hz）===
void MotionController::servo_pwm_init(uint8_t id, int gpio) {
    ledc_timer_config_t timer_conf = {};
    timer_conf.speed_mode = LEDC_LOW_SPEED_MODE;
    timer_conf.timer_num = LEDC_TIMER_0;
    timer_conf.duty_resolution = LEDC_TIMER_13_BIT;
    timer_conf.freq_hz = 50;  // 50Hz = 20ms 周期
    timer_conf.clk_cfg = LEDC_AUTO_CLK;
    ledc_timer_config(&timer_conf);

    ledc_channel_config_t ch_conf = {};
    ch_conf.gpio_num = gpio;
    ch_conf.speed_mode = LEDC_LOW_SPEED_MODE;
    ch_conf.channel = (ledc_channel_t)id;
    ch_conf.timer_sel = LEDC_TIMER_0;
    ch_conf.duty = 0;
    ledc_channel_config(&ch_conf);

    ESP_LOGI(TAG, "Servo[%d] GPIO%d → LEDC channel %d", id, gpio, id);
}

// === 设置舵机角度（脉宽映射）===
void MotionController::servo_pwm_set(uint8_t id, uint16_t pulse_us) {
    // 脉宽 → 占空比：duty = pulse_us / 20000 * 8192
    uint32_t duty = (uint32_t)pulse_us * 8192 / 20000;
    ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)id, duty);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)id);
}

void MotionController::ServoSet(uint8_t id, uint16_t angle, uint8_t speed) {
    if (!available_ || id >= 8) return;

    // 角度 → 脉宽：0°=500μs，180°=2500μs
    uint16_t pulse_us = 500 + (uint32_t)angle * 2000 / 180;
    pulse_us = (pulse_us < 500) ? 500 : (pulse_us > 2500) ? 2500 : pulse_us;
    servo_pwm_set(id, pulse_us);

    ESP_LOGI(TAG, "Servo[%d] → %d° (pulse=%dμs)", id, angle, pulse_us);
}

void MotionController::ServoBatch(const MotionAction *actions, int count) {
    for (int i = 0; i < count; i++) {
        if (actions[i].type == ActionType::SERVO_SET) {
            ServoSet(actions[i].params.servo.id,
                     actions[i].params.servo.angle,
                     actions[i].params.servo.speed);
        }
    }
}

void MotionController::ServoDisable(uint8_t id) {
    if (id >= 8) return;
    ledc_stop(LEDC_LOW_SPEED_MODE, (ledc_channel_t)id, 0);
    ESP_LOGI(TAG, "Servo[%d] disabled", id);
}

void MotionController::ServoDisableAll() {
    for (int i = 0; i < 8; i++) {
        ledc_stop(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i, 0);
    }
    ESP_LOGI(TAG, "All servos disabled");
}

// === 电机控制（差速转向）===
void MotionController::motor_pwm_init() {
    // TODO: 阶段三 — MCPWM 或 LEDC 初始化电机
    ESP_LOGI(TAG, "Motor PWM init (TODO)");
}

void MotionController::motor_set(int8_t left, int8_t right) {
    // TODO: 阶段三 — 设置左右电机速度
    ESP_LOGI(TAG, "Motor L=%d R=%d", left, right);
}

void MotionController::Move(int8_t direction, uint8_t speed) {
    if (!available_) return;
    uint8_t spd = (speed > max_speed_) ? max_speed_ : speed;
    motor_set(direction * spd, direction * spd);
}

void MotionController::Turn(int16_t angle, uint8_t speed) {
    if (!available_) return;
    // 正角度=右转，负角度=左转
    int8_t left = (angle > 0) ? speed : -speed;
    int8_t right = -left;
    motor_set(left, right);
    // TODO: 带编码器时精确控制角度
}

void MotionController::Stop() {
    motor_set(0, 0);
    ESP_LOGI(TAG, "Stopped");
}

void MotionController::EmergencyStop() {
    motor_set(0, 0);
    ServoDisableAll();
    ESP_LOGW(TAG, "Emergency stop!");
}

// === 高级动作 ===
void MotionController::WalkForward(uint8_t speed) { Move(1, speed); }
void MotionController::WalkBackward(uint8_t speed) { Move(-1, speed); }
void MotionController::TurnLeft(uint8_t speed) { Turn(-90, speed); }
void MotionController::TurnRight(uint8_t speed) { Turn(90, speed); }

void MotionController::Nod() {
    // 头部上下舵机快速动作
    ServoSet(0, 60, 80);   // 低头
    vTaskDelay(pdMS_TO_TICKS(300));
    ServoSet(0, 120, 80);  // 抬头
    vTaskDelay(pdMS_TO_TICKS(300));
    ServoSet(0, 90, 50);   // 回中
}

void MotionController::ShakeHead() {
    ServoSet(1, 60, 80);   // 左转
    vTaskDelay(pdMS_TO_TICKS(200));
    ServoSet(1, 120, 80);  // 右转
    vTaskDelay(pdMS_TO_TICKS(200));
    ServoSet(1, 90, 50);   // 回中
}

void MotionController::WaveHand() {
    ServoSet(2, 150, 70);  // 抬手
    vTaskDelay(pdMS_TO_TICKS(200));
    for (int i = 0; i < 3; i++) {
        ServoSet(2, 120, 90);
        vTaskDelay(pdMS_TO_TICKS(200));
        ServoSet(2, 150, 90);
        vTaskDelay(pdMS_TO_TICKS(200));
    }
    ServoSet(2, 90, 50);   // 收回
}

// === 动作序列执行 ===
static TaskHandle_t seq_task_handle = nullptr;

struct SeqContext {
    MotionController *ctrl;
    const MotionAction *actions;
    int count;
    MotionDoneCallback cb;
};

static void seq_task(void *arg) {
    auto *ctx = static_cast<SeqContext *>(arg);
    bool success = true;

    for (int i = 0; i < ctx->count; i++) {
        auto &a = ctx->actions[i];
        switch (a.type) {
            case ActionType::SERVO_SET:
                ctx->ctrl->ServoSet(a.params.servo.id, a.params.servo.angle, a.params.servo.speed);
                break;
            case ActionType::MOTOR_MOVE:
                ctx->ctrl->Move(a.params.motor.direction, a.params.motor.speed);
                break;
            case ActionType::MOTOR_TURN:
                ctx->ctrl->Turn(a.params.turn.angle, a.params.turn.speed);
                break;
            case ActionType::STOP:
                ctx->ctrl->Stop();
                break;
            case ActionType::WALK_FORWARD:
                ctx->ctrl->WalkForward(a.params.motor.speed);
                break;
            case ActionType::WALK_BACKWARD:
                ctx->ctrl->WalkBackward(a.params.motor.speed);
                break;
            case ActionType::TURN_LEFT:
                ctx->ctrl->TurnLeft(a.params.turn.speed);
                break;
            case ActionType::TURN_RIGHT:
                ctx->ctrl->TurnRight(a.params.turn.speed);
                break;
            case ActionType::NOD:
                ctx->ctrl->Nod();
                break;
            case ActionType::SHAKE_HEAD:
                ctx->ctrl->ShakeHead();
                break;
            case ActionType::WAVE_HAND:
                ctx->ctrl->WaveHand();
                break;
            case ActionType::WAIT:
                vTaskDelay(pdMS_TO_TICKS(a.params.wait.ms));
                break;
            default:
                ESP_LOGW(TAG, "Unknown action type: %d", (int)a.type);
                success = false;
                break;
        }
        if (a.duration_ms > 0) {
            vTaskDelay(pdMS_TO_TICKS(a.duration_ms));
        }
    }

    if (ctx->cb) ctx->cb(success);
    delete ctx;
    vTaskDelete(nullptr);
}

void MotionController::ExecuteSequence(const MotionAction *actions, int count, MotionDoneCallback cb) {
    if (!available_) {
        if (cb) cb(false);
        return;
    }
    auto *ctx = new SeqContext{this, actions, count, cb};
    xTaskCreate(seq_task, "motion_seq", 4096, ctx, 4, &seq_task_handle);
}

void MotionController::ParseAndExecute(const char *json_actions) {
    // TODO: 阶段三 — 解析 Agent 返回的 JSON 动作指令
    // 格式示例：{"actions":[{"type":"walk_forward","speed":50,"duration":2000},{"type":"turn_right","angle":90}]}
    ESP_LOGI(TAG, "ParseAndExecute: %s", json_actions);
}

// === 传感器 ===
float MotionController::GetDistance() {
    // TODO: 阶段三 — 超声波/红外测距
    return -1.0f;
}

void MotionController::GetIMU(float *accel, float *gyro) {
    // TODO: 阶段三 — MPU6050 读数
    if (accel) { accel[0] = accel[1] = accel[2] = 0; }
    if (gyro) { gyro[0] = gyro[1] = gyro[2] = 0; }
}

bool MotionController::IsObstacleDetected() {
    float dist = GetDistance();
    return (dist > 0 && dist < obstacle_min_cm_);
}
