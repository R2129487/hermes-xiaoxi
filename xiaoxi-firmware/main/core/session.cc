#include "session.h"
#include <cstring>

void Session::Init() { Clear(); }
void Session::Start() { Clear(); }

void Session::AddMessage(MessageRole role, const char *text) {
    if (count_ >= MAX_MESSAGES) {
        memmove(&msgs_[0], &msgs_[5], sizeof(SessionMessage) * 15);
        count_ = 15;
    }
    msgs_[count_].role = role;
    strncpy(msgs_[count_].text, text, sizeof(msgs_[count_].text) - 1);
    msgs_[count_].text[sizeof(msgs_[count_].text) - 1] = '\0';
    count_++;
}

int Session::GetMessages(SessionMessage *buf, int max_count) const {
    int n = (count_ < max_count) ? count_ : max_count;
    memcpy(buf, &msgs_[count_ - n], sizeof(SessionMessage) * n);
    return n;
}

void Session::Clear() {
    count_ = 0;
    memset(msgs_, 0, sizeof(msgs_));
}
