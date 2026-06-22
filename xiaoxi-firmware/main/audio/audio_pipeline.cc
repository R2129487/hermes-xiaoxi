#include "audio_pipeline.h"
#include "audio_codec.h"
#include <esp_log.h>
#include <cstring>
#include <algorithm>

static const char *TAG = "AudioPipeline";

AudioPipeline &AudioPipeline::GetInstance() {
    static AudioPipeline instance;
    return instance;
}

void AudioPipeline::Init(const AudioConfig &config) {
    config_ = config;
    if (codec_) {
        codec_->EnableInput(true);
        codec_->EnableOutput(true);
        codec_->Start();
    }
    ESP_LOGI(TAG, "Audio pipeline init: in=%dHz out=%dHz codec=%s",
             config.input_sample_rate, config.output_sample_rate,
             codec_ ? "yes" : "no");
}

void AudioPipeline::SetCodec(::AudioCodec *codec) {
    codec_ = codec;
}

void AudioPipeline::StartRecording() {
    recording_ = true;
    if (codec_) codec_->EnableInput(true);
    ESP_LOGI(TAG, "Recording started");
}

void AudioPipeline::StopRecording() {
    recording_ = false;
    ESP_LOGI(TAG, "Recording stopped");
}

int AudioPipeline::Read(int16_t *buf, int samples) {
    if (!codec_ || !recording_) return 0;
    std::vector<int16_t> data(samples);
    if (codec_->InputData(data)) {
        int actual = (int)data.size();
        if (actual > 0 && actual <= samples) {
            memcpy(buf, data.data(), actual * sizeof(int16_t));
            return actual;
        }
    }
    return 0;
}

// 录音并收集所有 PCM 数据（直到 VAD 检测到静音或超时）
// 注意：不自己管 StartRecording/StopRecording，
// 因为 voice_task 已经在后台持续录音
std::vector<int16_t> AudioPipeline::RecordUtterance(int max_seconds) {
    std::vector<int16_t> pcm;
    if (!codec_) return pcm;

    bool was_recording = recording_;
    // 确保录音已开启（如果 voice_task 没有开，这里补上）
    if (!was_recording) {
        StartRecording();
    }

    int max_samples = config_.input_sample_rate * max_seconds;
    int silence_count = 0;
    const int silence_threshold = 30;  // 30 帧静音 (~300ms)
    int frame_size = config_.input_sample_rate / 100;  // 10ms 一帧

    while ((int)pcm.size() < max_samples) {
        // 让出 CPU，避免空转
        if (!codec_) break;

        std::vector<int16_t> frame(frame_size);
        if (!codec_->InputData(frame)) {
            // 无数据时短暂休眠
            vTaskDelay(pdMS_TO_TICKS(5));
            continue;
        }

        // 计算帧能量
        int64_t energy = 0;
        for (auto s : frame) energy += (int64_t)s * s;
        energy /= frame.size();

        pcm.insert(pcm.end(), frame.begin(), frame.end());

        // 简单 VAD：能量低于阈值视为静音
        // 至少录 0.5 秒才允许停止
        if (energy < 100000) {
            silence_count++;
            if (silence_count > silence_threshold &&
                pcm.size() > (size_t)(config_.input_sample_rate * 0.5)) {
                ESP_LOGI(TAG, "VAD: silence after %zu samples (%.1fs)",
                         pcm.size(), (float)pcm.size() / config_.input_sample_rate);
                break;
            }
        } else {
            silence_count = 0;
        }
    }

    // 如果是我们自己开的录音，这里关掉
    if (!was_recording) {
        StopRecording();
    }
    return pcm;
}

// 播放 PCM 数据（带批量预分配，减少拷贝）
void AudioPipeline::Play(const int16_t *data, size_t samples) {
    if (!codec_ || !data || samples == 0) return;
    codec_->EnableOutput(true);

    const size_t chunk_size = 240;
    // 预分配临时缓冲区，避免每块都 new
    std::vector<int16_t> chunk;
    chunk.reserve(chunk_size);

    for (size_t i = 0; i < samples; i += chunk_size) {
        size_t n = std::min(chunk_size, samples - i);
        chunk.assign(data + i, data + i + n);
        codec_->OutputData(chunk);
    }
}

// VAD：检查是否有声音（非破坏性 — 读取的数据会放回内部缓冲区？不，我们不用这个方法，而是用 RecordUtterance）
// 注意：此方法会消耗一帧音频数据。调用者需知晓这个副作用。
// 如需要无副作用的检测，应使用 RecordUtterance 的 VAD 逻辑。
bool AudioPipeline::IsSpeaking() {
    if (!codec_ || !recording_) return false;

    int frame_size = config_.input_sample_rate / 100;
    std::vector<int16_t> frame(frame_size);
    if (!codec_->InputData(frame)) return false;

    int64_t energy = 0;
    for (auto s : frame) energy += (int64_t)s * s;
    energy /= frame.size();

    return energy >= 100000;
}
