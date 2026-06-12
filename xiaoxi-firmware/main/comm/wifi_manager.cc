#include "comm.h"
#include <esp_log.h>
#include <esp_wifi.h>
#include <esp_netif.h>
#include <esp_event.h>
#include <esp_mac.h>
#include <cstring>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static const char *TAG = "Wifi";

static esp_netif_t *s_sta_netif = nullptr;
static esp_netif_t *s_ap_netif = nullptr;
static TaskHandle_t s_reconnect_task = nullptr;

// 后台重连任务 — 不阻塞 WiFi 事件回调
static void reconnect_task(void *arg) {
    auto *self = static_cast<WifiManager *>(arg);
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        if (self->status_ == WifiStatus::DISCONNECTED) {
            ESP_LOGI(TAG, "Reconnecting...");
            esp_wifi_connect();
        }
    }
}

static void wifi_event_handler(void *arg, esp_event_base_t base,
                                int32_t event_id, void *event_data) {
    auto *self = static_cast<WifiManager *>(arg);

    if (base == WIFI_EVENT) {
        switch (event_id) {
            case WIFI_EVENT_STA_START:
                ESP_LOGI(TAG, "STA started, connecting...");
                esp_wifi_connect();
                break;
            case WIFI_EVENT_STA_DISCONNECTED: {
                ESP_LOGW(TAG, "Disconnected");
                self->status_ = WifiStatus::DISCONNECTED;
                // 不在这里 delay，交给后台任务重连
                break;
            }
            case WIFI_EVENT_STA_CONNECTED:
                ESP_LOGI(TAG, "Associated with AP");
                break;
            case WIFI_EVENT_AP_START:
                ESP_LOGI(TAG, "AP mode started");
                self->status_ = WifiStatus::AP_MODE;
                break;
            case WIFI_EVENT_AP_STACONNECTED: {
                auto *evt = (wifi_event_ap_staconnected_t *)event_data;
                ESP_LOGI(TAG, "Client connected: MAC=" MACSTR, MAC2STR(evt->mac));
                break;
            }
            default:
                break;
        }
    } else if (base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        auto *evt = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&evt->ip_info.ip));
        self->status_ = WifiStatus::CONNECTED;
    }
}

WifiManager &WifiManager::GetInstance() {
    static WifiManager i;
    return i;
}

void WifiManager::Init() {
    ESP_LOGI(TAG, "WiFi init");

    esp_netif_init();
    esp_event_loop_create_default();
    s_sta_netif = esp_netif_create_default_wifi_sta();
    s_ap_netif = esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);

    esp_event_handler_instance_t inst_any_id, inst_got_ip;
    esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                         &wifi_event_handler, this, &inst_any_id);
    esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                         &wifi_event_handler, this, &inst_got_ip);

    // 启动后台重连任务
    xTaskCreate(reconnect_task, "wifi_reconnect", 2048, this, 3, &s_reconnect_task);

    ESP_LOGI(TAG, "WiFi initialized");
}

void WifiManager::Connect(const char *ssid, const char *password, bool keep_ap) {
    ESP_LOGI(TAG, "Connect WiFi: %s (keep_ap=%d)", ssid, keep_ap);
    status_ = WifiStatus::CONNECTING;

    wifi_config_t wifi_cfg = {};
    strncpy((char *)wifi_cfg.sta.ssid, ssid, sizeof(wifi_cfg.sta.ssid) - 1);
    strncpy((char *)wifi_cfg.sta.password, password, sizeof(wifi_cfg.sta.password) - 1);
    wifi_cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    wifi_cfg.sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;

    if (keep_ap) {
        // APSTA 双模式：STA 连 WiFi 的同时保留 AP 热点
        wifi_config_t ap_cfg = {};
        strncpy((char *)ap_cfg.ap.ssid, "XiaoXi-Setup", sizeof(ap_cfg.ap.ssid) - 1);
        strncpy((char *)ap_cfg.ap.password, "xiaoxi88", sizeof(ap_cfg.ap.password) - 1);
        ap_cfg.ap.authmode = WIFI_AUTH_WPA2_PSK;
        ap_cfg.ap.max_connection = 4;
        ap_cfg.ap.channel = 1;

        esp_wifi_set_mode(WIFI_MODE_APSTA);
        esp_wifi_set_config(WIFI_IF_AP, &ap_cfg);
        ESP_LOGI(TAG, "APSTA mode: keeping XiaoXi-Setup hotspot");
    } else {
        esp_wifi_set_mode(WIFI_MODE_STA);
    }

    esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg);
    esp_wifi_start();
}

void WifiManager::StartAP(const char *ssid, const char *password) {
    ESP_LOGI(TAG, "AP mode: %s", ssid);
    status_ = WifiStatus::AP_MODE;

    wifi_config_t wifi_cfg = {};
    strncpy((char *)wifi_cfg.ap.ssid, ssid, sizeof(wifi_cfg.ap.ssid) - 1);
    if (password && password[0]) {
        strncpy((char *)wifi_cfg.ap.password, password, sizeof(wifi_cfg.ap.password) - 1);
        wifi_cfg.ap.authmode = WIFI_AUTH_WPA2_PSK;
    } else {
        wifi_cfg.ap.authmode = WIFI_AUTH_OPEN;
    }
    wifi_cfg.ap.max_connection = 4;
    wifi_cfg.ap.channel = 1;

    esp_wifi_set_mode(WIFI_MODE_AP);
    esp_wifi_set_config(WIFI_IF_AP, &wifi_cfg);
    esp_wifi_start();
}

void WifiManager::AutoConnect() {
}

bool WifiManager::IsConnected() const {
    return status_ == WifiStatus::CONNECTED;
}

const char *WifiManager::GetIP() const {
    if (!s_sta_netif || status_ != WifiStatus::CONNECTED) {
        return "0.0.0.0";
    }
    esp_netif_ip_info_t ip_info;
    if (esp_netif_get_ip_info(s_sta_netif, &ip_info) == ESP_OK) {
        static char ip_str[16];
        snprintf(ip_str, sizeof(ip_str), IPSTR, IP2STR(&ip_info.ip));
        return ip_str;
    }
    return "0.0.0.0";
}
