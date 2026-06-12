#pragma once
#include <cstdint>
#include <cstddef>
#include <functional>
#include <vector>

// === 模块 2：视觉 (Vision) ===
// 阶段二：ESP32-CAM 拍照 → 本地服务器 VLM（RoboBrain）理解场景

struct VisionConfig {
    int width = 640;
    int height = 480;
    int jpeg_quality = 80;  // 1-63，越低质量越高
    int fps = 10;
    bool stream_enabled = false;  // 视频流（阶段二后期）
};

struct VisionFrame {
    uint8_t *data = nullptr;
    size_t len = 0;
    uint32_t timestamp = 0;
};

using FrameCallback = std::function<void(const VisionFrame &frame)>;

// 场景理解结果
struct SceneAnalysis {
    char description[512] = {};   // 场景描述（RoboBrain 返回）
    char objects[256] = {};       // 识别到的物体
    char actions[256] = {};       // 建议动作
    float confidence = 0.0f;
};

using SceneCallback = std::function<void(const SceneAnalysis &analysis)>;

class Camera {
public:
    static Camera &GetInstance();

    void Init(const VisionConfig &config);
    bool IsAvailable() const { return available_; }

    // 拍照
    bool Capture(VisionFrame &frame);
    void ReleaseFrame(VisionFrame &frame);

    // 视频流
    void StartStream(FrameCallback callback);
    void StopStream();
    bool IsStreaming() const { return streaming_; }

    // 配置
    void SetResolution(int width, int height);
    void SetQuality(int quality);

    // === 阶段二新增：场景理解（VLM 调用）===

    // 拍照并发送到 Agent 做场景理解
    // question: 自然语言问题（"看看我面前是什么"）
    void CaptureAndAnalyze(const char *question, SceneCallback cb);

    // 连续观察模式（每 N 秒拍一张分析）
    void StartObserving(int interval_seconds, SceneCallback cb);
    void StopObserving();

    // 给 Agent 发送运动规划请求（阶段三）
    // jpeg_data: 当前帧, instruction: 指令（"往前走"、"向左转"）
    void PlanMotion(const uint8_t *jpeg_data, size_t jpeg_len,
                    const char *instruction, SceneCallback cb);

private:
    Camera() = default;
    bool available_ = false;
    bool streaming_ = false;
    bool observing_ = false;
    FrameCallback stream_cb_;
    SceneCallback observe_cb_;
    int width_ = 640;
    int height_ = 480;
    int quality_ = 80;
    int observe_interval_ = 5;

public:  // observe_task 需要访问
    int GetObserveInterval() const { return observe_interval_; }
    bool IsObserving() const { return observing_; }
};
