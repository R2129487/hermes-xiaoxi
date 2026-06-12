#pragma once
#include <cstdint>
#include <functional>

enum class DeviceState : uint8_t {
    IDLE = 0,
    LISTENING,
    THINKING,
    SPEAKING,
    CAPTURING,
    MOVING,
    CONFIG,
    ERROR,
};

using StateChangeCallback = std::function<void(DeviceState old_state, DeviceState new_state)>;

class StateMachine {
public:
    static StateMachine &GetInstance();

    void Init();
    DeviceState GetState() const { return state_; }
    bool Transition(DeviceState new_state);
    void OnChange(StateChangeCallback callback) { change_cb_ = std::move(callback); }
    static const char *StateName(DeviceState state);

private:
    StateMachine() = default;
    DeviceState state_ = DeviceState::IDLE;
    StateChangeCallback change_cb_;
};
