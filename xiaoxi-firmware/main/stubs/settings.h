// settings.h — 满足 xiaozhi-esp32 代码依赖
// 小智的 Settings 是 NVS key-value 封装
#pragma once
#include <string>
#include <nvs_flash.h>
#include <nvs.h>
#include <esp_log.h>

class Settings {
public:
    Settings(const char *namespace_name, bool read_write = false)
        : ns_(namespace_name), rw_(read_write), valid_(false) {
        esp_err_t err = nvs_open(ns_, rw_ ? NVS_READWRITE : NVS_READONLY, &handle_);
        valid_ = (err == ESP_OK);
    }
    ~Settings() { if (valid_) nvs_close(handle_); }

    int GetInt(const char *key, int default_val = 0) {
        if (!valid_) return default_val;
        int32_t val = default_val;
        nvs_get_i32(handle_, key, &val);
        return (int)val;
    }
    void SetInt(const char *key, int val) {
        if (!valid_ || !rw_) return;
        nvs_set_i32(handle_, key, val);
        nvs_commit(handle_);
    }
    std::string GetString(const char *key, const std::string &default_val = "") {
        if (!valid_) return default_val;
        size_t len = 0;
        nvs_get_str(handle_, key, nullptr, &len);
        if (len == 0) return default_val;
        std::string val(len, '\0');
        nvs_get_str(handle_, key, &val[0], &len);
        val.resize(len > 0 ? len - 1 : 0);
        return val;
    }
    void SetString(const char *key, const std::string &val) {
        if (!valid_ || !rw_) return;
        nvs_set_str(handle_, key, val.c_str());
        nvs_commit(handle_);
    }

private:
    const char *ns_;
    bool rw_;
    bool valid_;
    nvs_handle_t handle_ = 0;
};
