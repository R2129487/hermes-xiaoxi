#include "event_bus.h"
#include <esp_log.h>
#include <algorithm>

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

    if (!callback) {
        // callback 为空 = 移除该类型所有监听器
        for (int i = 0; i < count_[idx]; i++) {
            listeners_[idx][i] = nullptr;
        }
        count_[idx] = 0;
        return;
    }

    // 简单策略：移除该类型下的所有监听器
    // 注意：由于 std::function 不支持高效的比较操作，
    // 我们采用「清空并记录」的策略。
    // 当前使用场景中每个事件类型只有一个 listener，所以简化处理。
    if (count_[idx] > 0) {
        ESP_LOGD(TAG, "Removing all listeners for event type %d", idx);
        for (int i = 0; i < count_[idx]; i++) {
            listeners_[idx][i] = nullptr;
        }
        count_[idx] = 0;
    }
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
