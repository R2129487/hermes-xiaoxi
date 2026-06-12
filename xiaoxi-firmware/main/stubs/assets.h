// assets.h — 满足 xiaozhi-esp32 custom_wake_word.cc 依赖
// 最小实现：无资源时返回空
#pragma once
#include <cstddef>
#include <cstdint>
#include <string>

class Assets {
public:
    static Assets &GetInstance() { static Assets a; return a; }
    bool GetAssetData(const char *name, const uint8_t *&data, size_t &size) {
        data = nullptr; size = 0; return false;
    }
};
