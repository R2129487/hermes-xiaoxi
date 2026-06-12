#include "camera.h"
#include "comm/comm.h"
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static const char *TAG = "Camera";

Camera &Camera::GetInstance() {
    static Camera instance;
    return instance;
}

void Camera::Init(const VisionConfig &config) {
    width_ = config.width;
    height_ = config.height;
    quality_ = config.jpeg_quality;

    ESP_LOGI(TAG, "Camera init: %dx%d quality=%d fps=%d",
             width_, height_, quality_, config.fps);
    available_ = false;  // 等真正接上 ESP32-CAM 后改为 true
}

bool Camera::Capture(VisionFrame &frame) {
    if (!available_) return false;
    // TODO: 阶段二 — ESP32-CAM 拍照
    return false;
}

void Camera::ReleaseFrame(VisionFrame &frame) {
    if (frame.data) {
        free(frame.data);
        frame.data = nullptr;
        frame.len = 0;
    }
}

void Camera::StartStream(FrameCallback callback) {
    if (!available_) return;
    stream_cb_ = callback;
    streaming_ = true;
    // TODO: 阶段二 — 视频流任务
}

void Camera::StopStream() {
    streaming_ = false;
    stream_cb_ = nullptr;
}

void Camera::SetResolution(int width, int height) {
    width_ = width;
    height_ = height;
    ESP_LOGI(TAG, "Resolution set to %dx%d", width, height);
}

void Camera::SetQuality(int quality) {
    quality_ = quality;
}

// === 场景理解：拍照 → JPEG → Agent VisionQuery ===
void Camera::CaptureAndAnalyze(const char *question, SceneCallback cb) {
    if (!available_) {
        ESP_LOGW(TAG, "Camera not available");
        if (cb) {
            SceneAnalysis empty;
            snprintf(empty.description, sizeof(empty.description),
                     "摄像头未连接，无法识别场景。");
            cb(empty);
        }
        return;
    }

    ESP_LOGI(TAG, "Capture and analyze: %s", question);

    // TODO: 阶段二 — 真正的拍照 + VLM 调用
    // 流程：
    // 1. Capture(jpeg_frame)
    // 2. agent.VisionQuery(jpeg_frame.data, jpeg_frame.len, question)
    // 3. 解析返回 → SceneAnalysis
    // 4. cb(analysis)
}

// === 连续观察模式 ===
static TaskHandle_t observe_task_handle = nullptr;

static void observe_task(void *arg) {
    auto *self = static_cast<Camera *>(arg);

    while (self->IsObserving()) {
        if (self->IsAvailable()) {
            // TODO: 阶段二 — 周期性拍照分析
            ESP_LOGI(TAG, "Observing...");
        }
        vTaskDelay(pdMS_TO_TICKS(self->GetObserveInterval() * 1000));
    }
    vTaskDelete(nullptr);
}

void Camera::StartObserving(int interval_seconds, SceneCallback cb) {
    if (!available_ || observing_) return;
    observe_interval_ = interval_seconds;
    observe_cb_ = cb;
    observing_ = true;
    xTaskCreate(observe_task, "observe_task", 4096, this, 3, &observe_task_handle);
    ESP_LOGI(TAG, "Observing started, interval=%ds", interval_seconds);
}

void Camera::StopObserving() {
    observing_ = false;
    observe_cb_ = nullptr;
    observe_task_handle = nullptr;
}

// === 运动规划：拍照 + 指令 → Agent 返回动作 ===
void Camera::PlanMotion(const uint8_t *jpeg_data, size_t jpeg_len,
                        const char *instruction, SceneCallback cb) {
    if (!available_) {
        ESP_LOGW(TAG, "Camera not available for motion planning");
        return;
    }

    ESP_LOGI(TAG, "Planning motion: %s", instruction);

    // TODO: 阶段三 — 调用 Agent.MotionCommand()
    // agent.VisionQuery(jpeg_data, jpeg_len,
    //     "请分析当前场景并规划运动指令：...");
    // 解析返回 JSON → MotionAction 序列
}
