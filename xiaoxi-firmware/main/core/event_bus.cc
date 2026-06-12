#include "event_bus.h"
#include <esp_log.h>

static const char *TAG = "EventBus";

EventBus &EventBus::GetInstance() {
    static EventBus instance;
    return instance;
}

void EventBus::On(EventType type, EventCallback callback) {
    int idx = static_cast<int>(type);
    if (idx >= static_cast<int>(EventType::MAX) || !callback) return;
    if (count_[idx] >= MAX_LISTENERS) {
        ESP_LOGW(TAG, "Event %d listeners full", idx);
        return;
    }
    listeners_[idx][count_[idx]++] = std::move(callback);
}

void EventBus::Off(EventType type, EventCallback callback) {
    int idx = static_cast<int>(type);
    if (idx >= static_cast<int>(EventType::MAX)) return;
    for (int i = 0; i < count_[idx]; i++) {
        // 简单移除（标记为空）
        listeners_[idx][i] = nullptr;
    }
    count_[idx] = 0;
}

void EventBus::Emit(EventType type, const void *data, size_t data_len) {
    int idx = static_cast<int>(type);
    if (idx >= static_cast<int>(EventType::MAX)) return;
    Event event{type, data, data_len};
    for (int i = 0; i < count_[idx]; i++) {
        if (listeners_[idx][i]) {
            listeners_[idx][i](event);
        }
    }
}
