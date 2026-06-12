#include "output.h"
#include <esp_log.h>

static const char *TAG = "Output";

// === Player ===
Player &Player::GetInstance() { static Player i; return i; }

void Player::Init() {
    ESP_LOGI(TAG, "Player init");
    // TODO: 初始化 Opus 解码器
}

void Player::SetVolume(uint8_t volume) {
    volume_ = volume;
    ESP_LOGI(TAG, "Volume: %d", volume);
    // TODO: 设置 codec 音量
}

void Player::Play(const uint8_t *data, size_t len, PlayFormat format) {
    playing_ = true;
    // TODO: 解码并播放
}

void Player::Stop() { playing_ = false; }

void Player::StreamStart(PlayFormat format) {
    playing_ = true;
    // TODO: 初始化流式解码
}

void Player::StreamWrite(const uint8_t *data, size_t len) {
    // TODO: 写入流数据并解码播放
}

void Player::StreamStop() { playing_ = false; }

// === LedIndicator ===
LedIndicator &LedIndicator::GetInstance() { static LedIndicator i; return i; }

void LedIndicator::Init() {
    ESP_LOGI(TAG, "LED init");
    // TODO: 初始化 GPIO/LED 灯带
}

void LedIndicator::SetState(LedState state) {
    ESP_LOGD(TAG, "LED state: %d", static_cast<int>(state));
}

void LedIndicator::SetRGB(uint8_t r, uint8_t g, uint8_t b) { /* TODO */ }
void LedIndicator::SetBrightness(uint8_t brightness) { /* TODO */ }

// === Display ===
XiaoXiDisplay &XiaoXiDisplay::GetInstance() { static XiaoXiDisplay i; return i; }

void XiaoXiDisplay::Init() {
    ESP_LOGI(TAG, "Display init");
    available_ = false;  // TODO: 检测是否有屏幕
}

void XiaoXiDisplay::ShowText(const char *text) { /* TODO */ }
void XiaoXiDisplay::ShowEmotion(DisplayEmotion emotion) { /* TODO */ }
void XiaoXiDisplay::ShowStatus(const char *status) { /* TODO */ }
void XiaoXiDisplay::Clear() { /* TODO */ }
