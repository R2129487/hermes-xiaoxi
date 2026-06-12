#include "state_machine.h"
#include <esp_log.h>

static const char *TAG = "StateMachine";

static const char *STATE_NAMES[] = {
    "IDLE", "LISTENING", "THINKING", "SPEAKING",
    "CAPTURING", "MOVING", "CONFIG", "ERROR"
};

// 合法状态转换表
static const bool TRANSITION_TABLE[8][8] = {
    /*              IDLE  LIST  THINK SPEAK CAPT  MOVE  CONF  ERR  */
    /* IDLE    */ {  0,    1,    0,    0,    1,    0,    1,    1 },
    /* LISTEN  */ {  1,    0,    1,    0,    0,    0,    0,    1 },
    /* THINK   */ {  1,    0,    0,    1,    0,    1,    0,    1 },
    /* SPEAK   */ {  1,    1,    0,    0,    0,    0,    0,    1 },
    /* CAPT    */ {  1,    0,    1,    0,    0,    0,    0,    1 },
    /* MOVE    */ {  1,    0,    0,    1,    0,    0,    0,    1 },
    /* CONFIG  */ {  1,    0,    0,    0,    0,    0,    0,    1 },
    /* ERROR   */ {  1,    0,    0,    0,    0,    0,    1,    0 },
};

StateMachine &StateMachine::GetInstance() {
    static StateMachine instance;
    return instance;
}

void StateMachine::Init() {
    state_ = DeviceState::IDLE;
    ESP_LOGI(TAG, "State machine init: %s", StateName(state_));
}

bool StateMachine::Transition(DeviceState new_state) {
    int old_idx = static_cast<int>(state_);
    int new_idx = static_cast<int>(new_state);
    if (new_idx > static_cast<int>(DeviceState::ERROR)) return false;
    if (!TRANSITION_TABLE[old_idx][new_idx]) {
        ESP_LOGW(TAG, "Invalid transition: %s -> %s", StateName(state_), StateName(new_state));
        return false;
    }
    DeviceState old = state_;
    state_ = new_state;
    ESP_LOGI(TAG, "Transition: %s -> %s", StateName(old), StateName(new_state));
    if (change_cb_) change_cb_(old, new_state);
    return true;
}

const char *StateMachine::StateName(DeviceState state) {
    int idx = static_cast<int>(state);
    if (idx > static_cast<int>(DeviceState::ERROR)) return "UNKNOWN";
    return STATE_NAMES[idx];
}
