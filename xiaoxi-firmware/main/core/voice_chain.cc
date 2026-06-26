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
#include <freertos/semphr.h>
#include <atomic>

static const char *TAG = "VoiceChain";

static TaskHandle_t voice_task_handle = nullptr;
static std::atomic<bool> voice_active{false};
static std::atomic<bool> interaction_in_progress{false};
static SemaphoreHandle_t voice_shutdown_sem = nullptr;

// 使用堆分配替代栈分配，避免悬空指针
static EspWakeWord *s_wake_word = nullptr;
static std::mutex s_wake_word_mutex;

// === 带互斥锁的语音交互封装，防止重入 ===
void run_voice_interaction();

static void run_voice_interaction_with_wakeword() {
    // 防止重入：如果已经在交互中，直接忽略
    bool expected = false;
    if (!interaction_in_progress.compare_exchange_strong(expected, true)) {
        ESP_LOGW(TAG, "Interaction already in progress, ignoring");
        return;
    }

    // 交互期间停止唤醒词
    {
        std::lock_guard<std::mutex> lock(s_wake_word_mutex);
        if (s_wake_word) {
            s_wake_word->Stop();
        }
    }

    // 执行交互
    run_voice_interaction();

    // 交互完成后恢复唤醒词
    {
        std::lock_guard<std::mutex> lock(s_wake_word_mutex);
        if (s_wake_word && voice_active.load()) {
            s_wake_word->Start();
        }
    }

    interaction_in_progress.store(false);
}

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
                free(asr_text);  // 防止多次回调
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
        asr_text = nullptr;
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
            (void)token;
        },
        .on_llm_done = [&](const char *full_text) {
            if (full_text) {
                free(llm_reply);  // 防止多次回调
                llm_reply = strdup(full_text);
                ESP_LOGI(TAG, "LLM 回复: %s", full_text);
            }
        },
        .on_tts_audio = nullptr,
    });
    agent.Chat(msgs, 2);

    free(asr_text);
    asr_text = nullptr;

    if (!llm_reply || !llm_reply[0]) {
        ESP_LOGW(TAG, "LLM 返回空");
        free(llm_reply);
        llm_reply = nullptr;
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
    llm_reply = nullptr;

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

// === 后台语音任务 ===
// 持续读取音频 → 喂给唤醒词检测 → 唤醒后触发语音交互
static void voice_task(void *arg) {
    auto &audio = AudioPipeline::GetInstance();
    auto &board = XiaoXiBoard::GetInstance();

    ESP_LOGI(TAG, "Voice task started");

    // 堆分配唤醒词对象，避免悬空指针
    EspWakeWord *wake_word = new (std::nothrow) EspWakeWord();
    if (!wake_word) {
        ESP_LOGE(TAG, "Failed to allocate wake word detector");
        ESP_LOGI(TAG, "Falling back to button-only mode");
    } else {
        // 初始化唤醒词
        if (!wake_word->Initialize(nullptr, nullptr)) {
            ESP_LOGE(TAG, "Failed to initialize wake word detection");
            ESP_LOGI(TAG, "Falling back to button-only mode");
            delete wake_word;
            wake_word = nullptr;
        } else {
            // 注册唤醒回调
            wake_word->OnWakeWordDetected([](const std::string &ww) {
                ESP_LOGI(TAG, "Wake word detected: %s", ww.c_str());
                run_voice_interaction_with_wakeword();
            });
            // 原子性地注册全局唤醒词指针（在Start之前，避免竞态）
            {
                std::lock_guard<std::mutex> lock(s_wake_word_mutex);
                s_wake_word = wake_word;
            }
            wake_word->Start();
            ESP_LOGI(TAG, "Wake word detection started: '你好小鑫'");
        }
    }

    // 注册按钮回调（使用带重入保护的封装）
    board.RegisterButtonCallback([]() {
        ESP_LOGI(TAG, "Button triggered");
        run_voice_interaction_with_wakeword();
    });

    // 主循环：持续读取音频喂给唤醒词
    size_t feed_size = 320; // 默认 20ms @ 16kHz
    if (wake_word) {
        size_t ww_feed = wake_word->GetFeedSize();
        if (ww_feed > 0) {
            feed_size = ww_feed;
        }
    }

    // 后台持续录音用于唤醒词馈送
    audio.StartRecording();

    while (voice_active.load()) {
        if (wake_word) {
            std::vector<int16_t> frame(feed_size);
            int n = audio.Read(frame.data(), feed_size);
            if (n > 0) {
                frame.resize(n);
                {
                    std::lock_guard<std::mutex> lock(s_wake_word_mutex);
                    if (wake_word) {
                        wake_word->Feed(frame);
                    }
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    audio.StopRecording();

    // 清理：先锁再释放
    {
        std::lock_guard<std::mutex> lock(s_wake_word_mutex);
        if (wake_word) {
            wake_word->Stop();
        }
        s_wake_word = nullptr;
    }

    delete wake_word;

    // 通知停止完成
    if (voice_shutdown_sem) {
        xSemaphoreGive(voice_shutdown_sem);
    }

    voice_task_handle = nullptr;
    vTaskDelete(nullptr);
}

// === 启动语音任务 ===
void start_voice_task() {
    if (voice_active.load()) {
        ESP_LOGW(TAG, "Voice task already running");
        return;
    }

    // 创建停止同步信号量
    if (voice_shutdown_sem == nullptr) {
        voice_shutdown_sem = xSemaphoreCreateBinary();
    }

    voice_active.store(true);
    BaseType_t ret = xTaskCreate(voice_task, "voice_task", 8192, nullptr, 5, &voice_task_handle);
    if (ret != pdTRUE) {
        ESP_LOGE(TAG, "Failed to create voice task");
        voice_active.store(false);
        return;
    }
    ESP_LOGI(TAG, "Voice task started");
}

// === 停止语音任务（带同步等待）===
void stop_voice_task() {
    if (!voice_active.load()) return;

    voice_active.store(false);

    // 等待任务退出（最多等 3 秒）
    if (voice_task_handle && voice_shutdown_sem) {
        if (xSemaphoreTake(voice_shutdown_sem, pdMS_TO_TICKS(3000)) != pdTRUE) {
            ESP_LOGW(TAG, "Voice task did not stop in time, forcing");
        }
    }

    voice_task_handle = nullptr;
    ESP_LOGI(TAG, "Voice task stopped");
}
