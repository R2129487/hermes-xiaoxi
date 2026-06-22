#include "camera.h"
#include "comm/comm.h"
#include <esp_log.h>
#include <esp_err.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/semphr.h>
#include <freertos/queue.h>
#include <string.h>

#include "usb/usb_host.h"
#include "usb/uvc_host.h"

static const char *TAG = "Camera";

// UVC 配置
#define USB_HOST_TASK_PRIORITY      5
#define USB_HOST_TASK_STACK_SIZE    4096
#define UVC_TASK_PRIORITY           8
#define UVC_TASK_STACK_SIZE         4096
#define UVC_FRAME_COUNT             3
#define UVC_STREAM_TIMEOUT_MS       5000

// UVC 状态
static bool s_usb_installed = false;
static bool s_uvc_installed = false;
static TaskHandle_t s_usb_task_handle = NULL;
static TaskHandle_t s_uvc_frame_task = NULL;
static QueueHandle_t s_frame_queue = NULL;
static SemaphoreHandle_t s_capture_done = NULL;
static uvc_host_frame_t *s_captured_frame = NULL;
static bool s_capture_success = false;

// === USB 事件处理任务 ===
static void usb_lib_task(void *arg) {
    while (true) {
        uint32_t event_flags;
        esp_err_t ret = usb_host_lib_handle_events(portMAX_DELAY, &event_flags);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "USB event handling failed: %s", esp_err_to_name(ret));
            break;
        }
        if (event_flags & USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS) {
            usb_host_device_free_all();
        }
        if (event_flags & USB_HOST_LIB_EVENT_FLAGS_ALL_FREE) {
            ESP_LOGI(TAG, "USB: All devices freed");
        }
    }
    s_usb_task_handle = NULL;
    vTaskDelete(NULL);
}

// === 帧回调：收到帧就放队列 ===
static bool frame_callback(const uvc_host_frame_t *frame, void *user_ctx) {
    QueueHandle_t frame_q = *((QueueHandle_t *)user_ctx);
    BaseType_t result = xQueueSendToBack(frame_q, &frame, 0);
    if (pdPASS != result) {
        ESP_LOGW(TAG, "Frame queue full, dropping frame");
        return true;
    }
    return false;
}

// === 流事件回调 ===
static void stream_callback(const uvc_host_stream_event_data_t *event, void *user_ctx) {
    switch (event->type) {
    case UVC_HOST_TRANSFER_ERROR:
        ESP_LOGE(TAG, "USB transfer error: %d", event->transfer_error.error);
        break;
    case UVC_HOST_DEVICE_DISCONNECTED:
        ESP_LOGI(TAG, "UVC device disconnected");
        break;
    case UVC_HOST_FRAME_BUFFER_OVERFLOW:
        ESP_LOGW(TAG, "Frame buffer overflow");
        break;
    case UVC_HOST_FRAME_BUFFER_UNDERFLOW:
        ESP_LOGW(TAG, "Frame buffer underflow");
        break;
    default:
        break;
    }
}

// === 帧处理任务（拍照用） ===
static void capture_frame_task(void *arg) {
    (void)arg;
    QueueHandle_t frame_q = s_frame_queue;

    // 用配置参数打开 UVC 流
    const uvc_host_stream_config_t stream_config = {
        .event_cb = stream_callback,
        .frame_cb = frame_callback,
        .user_ctx = &frame_q,
        .usb = {
            .dev_addr = UVC_HOST_ANY_DEV_ADDR,
            .vid = UVC_HOST_ANY_VID,
            .pid = UVC_HOST_ANY_PID,
            .uvc_stream_index = 0,
        },
        .vs_format = {
            .h_res = 640,
            .v_res = 480,
            .fps = 15,
            .format = UVC_VS_FORMAT_MJPEG,
        },
        .advanced = {
            .number_of_frame_buffers = UVC_FRAME_COUNT,
        },
    };

    ESP_LOGI(TAG, "Opening UVC stream...");
    uvc_host_stream_hdl_t uvc_stream = NULL;
    esp_err_t err = uvc_host_stream_open(&stream_config, pdMS_TO_TICKS(UVC_STREAM_TIMEOUT_MS), &uvc_stream);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open UVC stream: %s", esp_err_to_name(err));
        s_capture_success = false;
        if (s_capture_done) xSemaphoreGive(s_capture_done);
        vTaskDelete(NULL);
        return;
    }
    ESP_LOGI(TAG, "UVC stream opened!");

    // 启动流
    err = uvc_host_stream_start(uvc_stream);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start UVC stream: %s", esp_err_to_name(err));
        uvc_host_stream_close(uvc_stream);
        s_capture_success = false;
        if (s_capture_done) xSemaphoreGive(s_capture_done);
        vTaskDelete(NULL);
        return;
    }

    // 等一帧
    uvc_host_frame_t *frame = NULL;
    if (xQueueReceive(frame_q, &frame, pdMS_TO_TICKS(UVC_STREAM_TIMEOUT_MS)) == pdPASS) {
        ESP_LOGI(TAG, "Frame captured: %dx%d, len=%d",
                 frame->vs_format.h_res, frame->vs_format.v_res, frame->data_len);
        s_captured_frame = frame;
        s_capture_success = true;
    } else {
        ESP_LOGW(TAG, "No frame received");
        s_capture_success = false;
    }

    // 停止流
    uvc_host_stream_stop(uvc_stream);
    uvc_host_stream_close(uvc_stream);

    if (s_capture_done) {
        xSemaphoreGive(s_capture_done);
    }
    vTaskDelete(NULL);
}

// ==================== Camera 接口实现 ====================

Camera &Camera::GetInstance() {
    static Camera instance;
    return instance;
}

void Camera::Init(const VisionConfig &config) {
    width_ = config.width;
    height_ = config.height;
    quality_ = config.jpeg_quality;

    ESP_LOGI(TAG, "Camera init: %dx%d quality=%d", width_, height_, quality_);

    // 1. 安装 USB 主机库
    if (!s_usb_installed) {
        const usb_host_config_t host_config = {
            .skip_phy_setup = false,
            .intr_flags = ESP_INTR_FLAG_LOWMED,
        };
        esp_err_t ret = usb_host_install(&host_config);
        if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
            ESP_LOGE(TAG, "USB host install failed: %s", esp_err_to_name(ret));
            return;
        }

        // 启动 USB 事件任务
        BaseType_t task_ret = xTaskCreatePinnedToCore(usb_lib_task, "usb_host",
            USB_HOST_TASK_STACK_SIZE, NULL, USB_HOST_TASK_PRIORITY,
            &s_usb_task_handle, 0);
        if (task_ret != pdTRUE) {
            ESP_LOGE(TAG, "Failed to create USB task");
            usb_host_uninstall();
            return;
        }
        s_usb_installed = true;
        ESP_LOGI(TAG, "USB host installed");
    }

    // 2. 安装 UVC 驱动
    if (!s_uvc_installed) {
        const uvc_host_driver_config_t uvc_config = {
            .driver_task_stack_size = UVC_TASK_STACK_SIZE,
            .driver_task_priority = UVC_TASK_PRIORITY,
            .xCoreID = 0,
            .create_background_task = true,
            .event_cb = NULL,
            .user_ctx = NULL,
        };
        esp_err_t ret = uvc_host_install(&uvc_config);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "UVC driver install failed: %s", esp_err_to_name(ret));
            return;
        }
        s_uvc_installed = true;
        ESP_LOGI(TAG, "UVC driver installed");
    }

    // 3. 创建帧队列和信号量
    if (s_frame_queue == NULL) {
        s_frame_queue = xQueueCreate(UVC_FRAME_COUNT, sizeof(uvc_host_frame_t *));
    }
    if (s_capture_done == NULL) {
        s_capture_done = xSemaphoreCreateBinary();
    }

    available_ = true;
    ESP_LOGI(TAG, "Camera initialized successfully");
}

bool Camera::Capture(VisionFrame &frame) {
    if (!available_) {
        ESP_LOGW(TAG, "Camera not available");
        return false;
    }

    s_capture_success = false;
    s_captured_frame = NULL;

    // 确保信号量初始为0
    xSemaphoreTake(s_capture_done, 0);

    // 启动拍照任务
    BaseType_t task_ret = xTaskCreatePinnedToCore(capture_frame_task, "uvc_capture",
        UVC_TASK_STACK_SIZE * 2, NULL, UVC_TASK_PRIORITY, &s_uvc_frame_task, 0);
    if (task_ret != pdTRUE) {
        ESP_LOGE(TAG, "Failed to create capture task");
        return false;
    }

    // 等拍照完成（最多6秒）
    if (xSemaphoreTake(s_capture_done, pdMS_TO_TICKS(UVC_STREAM_TIMEOUT_MS + 2000)) == pdTRUE) {
        if (s_capture_success && s_captured_frame) {
            // 拷贝帧数据
            frame.data = (uint8_t *)malloc(s_captured_frame->data_len);
            if (frame.data) {
                memcpy(frame.data, s_captured_frame->data, s_captured_frame->data_len);
                frame.len = s_captured_frame->data_len;
                frame.timestamp = (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
            }
            // 归还帧
            // 注意：这里没有 uvc_stream handle 了，但 frame 必须归还
            // 简化处理：我们已经在 capture_frame_task 中关闭了流
            uvc_host_frame_return(NULL, s_captured_frame);
            return frame.data != NULL;
        }
    }

    ESP_LOGW(TAG, "Capture timeout or failed");
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
    ESP_LOGW(TAG, "Video streaming not implemented yet");
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

// === 场景理解（未实现，留空）===
void Camera::CaptureAndAnalyze(const char *question, SceneCallback cb) {
    ESP_LOGW(TAG, "CaptureAndAnalyze not implemented");
    if (cb) {
        SceneAnalysis empty = {};
        cb(empty);
    }
}

void Camera::StartObserving(int interval_seconds, SceneCallback cb) {
    ESP_LOGW(TAG, "StartObserving not implemented");
}

void Camera::StopObserving() {
    ESP_LOGW(TAG, "StopObserving not implemented");
}

void Camera::PlanMotion(const uint8_t *jpeg_data, size_t jpeg_len,
                        const char *instruction, SceneCallback cb) {
    ESP_LOGW(TAG, "PlanMotion not implemented");
    if (cb) {
        SceneAnalysis empty = {};
        cb(empty);
    }
}
