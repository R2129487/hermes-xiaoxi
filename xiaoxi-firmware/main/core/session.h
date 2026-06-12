#pragma once
#include <cstdint>
#include <cstring>

enum class MessageRole : uint8_t { USER, ASSISTANT };

struct SessionMessage {
    MessageRole role;
    char text[512];
};

class Session {
public:
    static constexpr int MAX_MESSAGES = 20;

    void Init();
    void Start();
    void AddMessage(MessageRole role, const char *text);
    int GetMessages(SessionMessage *buf, int max_count) const;
    void Clear();
    int Count() const { return count_; }

private:
    SessionMessage msgs_[MAX_MESSAGES] = {};
    int count_ = 0;
};
