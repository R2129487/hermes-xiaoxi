#include "esp_wake_word.h"
#include <esp_log.h>


#define TAG "EspWakeWord"

EspWakeWord::EspWakeWord() {
}

EspWakeWord::~EspWakeWord() {
    if (wakenet_data_ != nullptr) {
        wakenet_iface_->destroy(wakenet_data_);
        esp_srmodel_deinit(wakenet_model_);
    }
}

bool EspWakeWord::Initialize(AudioCodec* codec, srmodel_list_t* models_list) {
    codec_ = codec;

    if (models_list == nullptr) {
        wakenet_model_ = esp_srmodel_init("model");
    } else {
        wakenet_model_ = models_list;
    }

    if (wakenet_model_ == nullptr || wakenet_model_->num == -1) {
        ESP_LOGE(TAG, "Failed to initialize wakenet model");
        return false;
    }
    if(wakenet_model_->num > 1) {
        ESP_LOGW(TAG, "More than one model found, using the first one");
    } else if (wakenet_model_->num == 0) {
        ESP_LOGE(TAG, "No model found");
        return false;
    }
    char *model_name = wakenet_model_->model_name[0];
    wakenet_iface_ = (esp_wn_iface_t*)esp_wn_handle_from_name(model_name);
    wakenet_data_ = wakenet_iface_->create(model_name, DET_MODE_95);

    int frequency = wakenet_iface_->get_samp_rate(wakenet_data_);
    int audio_chunksize = wakenet_iface_->get_samp_chunksize(wakenet_data_);
    ESP_LOGI(TAG, "Wake word(%s),freq: %d, chunksize: %d", model_name, frequency, audio_chunksize);

    return true;
}

void EspWakeWord::OnWakeWordDetected(std::function<void(const std::string& wake_word)> callback) {
    wake_word_detected_callback_ = callback;
}

void EspWakeWord::Start() {
    running_ = true;
}

void EspWakeWord::Stop() {
    running_ = false;

    std::lock_guard<std::mutex> lock(input_buffer_mutex_);
    input_buffer_.clear();
}

void EspWakeWord::Feed(const std::vector<int16_t>& data) {
    if (wakenet_data_ == nullptr) {
        return;
    }

    // 先检查 running 状态（快速路径，无锁）
    if (!running_.load()) {
        return;
    }

    std::string detected_word;
    bool detected = false;

    // 用大括号控制临界区范围，确保调用回调时已释放锁
    {
        std::lock_guard<std::mutex> lock(input_buffer_mutex_);

        // 在锁内再次检查 running 状态（防止 TOCTOU 竞态）
        if (!running_) {
            return;
        }

        // 声道转换（双声道取左声道）
        if (codec_ != nullptr && codec_->input_channels() == 2) {
            for (size_t i = 0; i < data.size(); i += 2) {
                input_buffer_.push_back(data[i]);
            }
        } else {
            input_buffer_.insert(input_buffer_.end(), data.begin(), data.end());
        }

        // 逐块检测唤醒词
        int chunksize = wakenet_iface_->get_samp_chunksize(wakenet_data_);
        while (input_buffer_.size() >= (size_t)chunksize) {
            int res = wakenet_iface_->detect(wakenet_data_, input_buffer_.data());
            if (res > 0) {
                detected_word = wakenet_iface_->get_word_name(wakenet_data_, res);
                running_ = false;
                input_buffer_.clear();
                detected = true;
                break;
            }
            input_buffer_.erase(input_buffer_.begin(), input_buffer_.begin() + chunksize);
        }

        if (detected) {
            last_detected_wake_word_ = detected_word;
        }
    }
    // 此时 input_buffer_mutex_ 已释放

    // 在锁外调用回调，防止死锁（回调可能尝试获取同一个 mutex）
    if (detected && wake_word_detected_callback_) {
        wake_word_detected_callback_(detected_word);
    }
}

size_t EspWakeWord::GetFeedSize() {
    if (wakenet_data_ == nullptr) {
        return 0;
    }
    return wakenet_iface_->get_samp_chunksize(wakenet_data_);
}

void EspWakeWord::EncodeWakeWordData() {
}

bool EspWakeWord::GetWakeWordOpus(std::vector<uint8_t>& opus) {
    return false;
}
