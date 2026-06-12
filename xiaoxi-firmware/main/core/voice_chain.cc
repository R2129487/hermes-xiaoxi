#include "event_bus.h"
#include "state_machine.h"
#include "config.h"
#include "session.h"
#include "audio/audio_pipeline.h"
#include "audio/wake_words/esp_wake_word.h"
#include "comm/comm.h"
#include "output/output.h"
#include "hal/board.h"
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static const char *TAG = "VoiceChain";

static TaskHandle_t voice_task_handle = nullptr;
static volatile bool voice_active = false;
static EspWakeWord *s_wake_word = nullptr;

// === 一次完整的语音交互（录音 → ASR → Chat → TTS → 播放）===
void run_voice_interaction() {
    auto &audio = AudioPipeline::GetInstance();
    auto &agent = AgentClient::GetInstance();
    auto &sm = StateMachine::GetInstance();
    auto &led = LedIndicator::GetInstance();

    if (agent.IsBusy()) {
        ESP_LOGW(TAG, "Agent busy, skip");
        return;
    }

    // 1. 进入录音状态
    sm.Transition(DeviceState::LISTENING);
    led.SetState(LedState::LISTENING);
    // todo: PlayBeep(BeepType::START_LISTEN);
    ESP_LOGI(TAG, "=== 开始录音 ===");

    // 2. 录音（VAD 自动检测说完）
    std::vector<int16_t> pcm = audio.RecordUtterance(10);
    if (pcm.empty()) {
        ESP_LOGW(TAG, "No audio captured");
        sm.Transition(DeviceState::IDLE);
        led.SetState(LedState::IDLE);
        return;
    }
    ESP_LOGI(TAG, "录到 %zu 样本 (%.1f秒)", pcm.size(),
             (float)pcm.size() / 16000);

    // 3. ASR：语音转文字
    sm.Transition(DeviceState::THINKING);
    led.SetState(LedState::THINKING);
    ESP_LOGI(TAG, "=== ASR 识别中 ===");

    char *asr_text = nullptr;
    agent.SetCallbacks({
        .on_asr = [&](const char *text) {
            if (text && text[0]) {
                asr_text = strdup(text);
                ESP_LOGI(TAG, "ASR 结果: %s", text);
            }
        },
        .on_llm_token = nullptr,
        .on_llm_done = nullptr,
        .on_tts_audio = nullptr,
    });
    agent.Asr((const uint8_t *)pcm.data(), pcm.size() * 2, 16000);

    if (!asr_text || !asr_text[0]) {
        ESP_LOGW(TAG, "ASR 返回空");
        free(asr_text);
        sm.Transition(DeviceState::IDLE);
        led.SetState(LedState::IDLE);
        return;
    }

    // 4. Chat：发送到 Agent
    ESP_LOGI(TAG, "=== Chat 对话中 ===");
    AgentMessage msgs[2];
    msgs[0] = {"system", "你是小希，一个可爱的AI语音助手。用简短自然的中文回答。"};
    msgs[1] = {"user", asr_text};

    char *llm_reply = nullptr;
    agent.SetCallbacks({
        .on_asr = nullptr,
        .on_llm_token = [&](const char *token) {
            // 流式 token（可做实时显示或闪烁提示）
        },
        .on_llm_done = [&](const char *full_text) {
            if (full_text) {
                llm_reply = strdup(full_text);
                ESP_LOGI(TAG, "LLM 回复: %s", full_text);
            }
        },
        .on_tts_audio = nullptr,
    });
    agent.Chat(msgs, 2);

    free(asr_text);

    if (!llm_reply || !llm_reply[0]) {
        ESP_LOGW(TAG, "LLM 返回空");
        free(llm_reply);
        sm.Transition(DeviceState::IDLE);
        led.SetState(LedState::IDLE);
        return;
    }

    // 5. TTS：文字转语音
    sm.Transition(DeviceState::SPEAKING);
    led.SetState(LedState::SPEAKING);
    ESP_LOGI(TAG, "=== TTS 合成中 ===");

    std::vector<uint8_t> tts_data;
    agent.SetCallbacks({
        .on_asr = nullptr,
        .on_llm_token = nullptr,
        .on_llm_done = nullptr,
        .on_tts_audio = [&](const uint8_t *data, size_t len) {
            tts_data.insert(tts_data.end(), data, data + len);
        },
    });
    agent.Tts(llm_reply);
    free(llm_reply);

    // 6. 播放 TTS 回复
    if (!tts_data.empty()) {
        ESP_LOGI(TAG, "=== 播放回复 (%zu bytes) ===", tts_data.size());
        audio.Play((const int16_t *)tts_data.data(), tts_data.size() / 2);
    }

    // 7. 回到待机
    sm.Transition(DeviceState::IDLE);
    led.SetState(LedState::IDLE);
    ESP_LOGI(TAG, "=== 交互完成 ===");
}

// === 带唤醒词恢复的语音交互封装 ===
// run_voice_interaction 里不处理恢复唤醒词，
// 因为多处 return，在这层统一处理
static void run_voice_interaction_with_wakeword() {
    // 交互期间停止唤醒词
    if (s_wake_word) {
        s_wake_word->Stop();
    }
    run_voice_interaction();
    // 交互完成后恢复唤醒词
    if (s_wake_word) {
        s_wake_word->Start();
    }
}

// === 后台语音任务 ===
// 持续读取音频 → 喂给唤醒词检测 → 唤醒后触发语音交互
static void voice_task(void *arg) {
    auto &audio = AudioPipeline::GetInstance();
    auto &board = XiaoXiBoard::GetInstance();
    EspWakeWord wake_word;

    ESP_LOGI(TAG, "Voice task started");

    // 初始化唤醒词（传 nullptr codec，Feed 方法中仅用于声道判断，已做 null 安全）
    if (!wake_word.Initialize(nullptr, nullptr)) {
        ESP_LOGE(TAG, "Failed to initialize wake word detection");
        ESP_LOGI(TAG, "Falling back to button-only mode");
    } else {
        s_wake_word = &wake_word;
        // 注册唤醒回调
        wake_word.OnWakeWordDetected([](const std::string &ww) {
            ESP_LOGI(TAG, "Wake word detected: %s", ww.c_str());
            run_voice_interaction_with_wakeword();
        });
        wake_word.Start();
        ESP_LOGI(TAG, "Wake word detection started: '你好小鑫'");
    }

    // 注册按钮回调
    board.RegisterButtonCallback([]() {
        ESP_LOGI(TAG, "Button triggered");
        run_voice_interaction_with_wakeword();
    });

    // 主循环：持续读取音频喂给唤醒词
    size_t feed_size = wake_word.GetFeedSize();
    if (feed_size == 0) {
        feed_size = 320; // 默认 20ms @ 16kHz
    }

    // 后台持续录音用于唤醒词馈送
    audio.StartRecording();

    while (voice_active) {
        if (s_wake_word != nullptr) {
            std::vector<int16_t> frame(feed_size);
            int n = audio.Read(frame.data(), feed_size);
            if (n > 0) {
                frame.resize(n);
                s_wake_word->Feed(frame);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    audio.StopRecording();
    if (s_wake_word) {
        s_wake_word->Stop();
    }
    s_wake_word = nullptr;
    vTaskDelete(nullptr);
}

// === 启动语音任务 ===
void start_voice_task() {
    if (voice_active) {
        ESP_LOGW(TAG, "Voice task already running");
        return;
    }
    voice_active = true;
    xTaskCreate(voice_task, "voice_task", 8192, nullptr, 5, &voice_task_handle);
    ESP_LOGI(TAG, "Voice task started");
}

// === 停止语音任务 ===
void stop_voice_task() {
    if (!voice_active) return;
    voice_active = false;
    if (voice_task_handle) {
        vTaskDelay(pdMS_TO_TICKS(200));
        voice_task_handle = nullptr;
    }
    ESP_LOGI(TAG, "Voice task stopped");
}
