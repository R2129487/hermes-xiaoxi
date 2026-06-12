#include "config.h"
#include <nvs_flash.h>
#include <nvs.h>
#include <esp_log.h>

static const char *TAG = "Config";
static const char *NS = "xiaoxi";

Config &Config::GetInstance() {
    static Config instance;
    return instance;
}

void Config::Init() {
    // NVS Flash 初始化（首次使用）
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS partition full/changed, erasing...");
        nvs_flash_erase();
        nvs_flash_init();
    }
    Load();
    ESP_LOGI(TAG, "Config init: device=%s", cfg_.device_name);
    ESP_LOGI(TAG, "  Chat:   %s [%s]", GetChatUrl(), cfg_.chat.model);
    ESP_LOGI(TAG, "  ASR:    %s [%s]", GetAsrUrl(), cfg_.asr.model);
    ESP_LOGI(TAG, "  TTS:    %s [%s]", GetTtsUrl(), cfg_.tts.model);
    ESP_LOGI(TAG, "  Vision: %s", GetVisionUrl());
}

void Config::Save() {
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READWRITE, &h) != ESP_OK) {
        ESP_LOGE(TAG, "NVS open failed");
        return;
    }
    nvs_set_blob(h, "config", &cfg_, sizeof(cfg_));
    nvs_commit(h);
    nvs_close(h);
    ESP_LOGI(TAG, "Config saved");
}

void Config::Load() {
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READONLY, &h) != ESP_OK) {
        ESP_LOGW(TAG, "NVS empty, using defaults");
        return;
    }
    size_t len = sizeof(cfg_);
    if (nvs_get_blob(h, "config", &cfg_, &len) != ESP_OK) {
        ESP_LOGW(TAG, "NVS read failed, using defaults");
        cfg_ = XiaoXiConfig{};
    }
    nvs_close(h);
}

// === URL 获取：独立配置优先，fallback 到通用 agent_url ===

const char *Config::GetChatUrl() const {
    if (cfg_.chat.url[0]) return cfg_.chat.url;
    return cfg_.agent_url;
}

const char *Config::GetAsrUrl() const {
    if (cfg_.asr.url[0]) return cfg_.asr.url;
    return cfg_.agent_url;
}

const char *Config::GetTtsUrl() const {
    if (cfg_.tts.url[0]) return cfg_.tts.url;
    return cfg_.agent_url;
}

const char *Config::GetVisionUrl() const {
    if (cfg_.vision.url[0]) return cfg_.vision.url;
    return cfg_.agent_url;
}
