#include "comm.h"
#include "core/config.h"
#include <esp_log.h>
#include <esp_http_client.h>
#include <esp_http_server.h>
#include <esp_system.h>
#include <freertos/task.h>
#include <cstring>
#include <string>
#include <cJSON.h>
#include <lwip/sockets.h>
#include <netinet/in.h>

static const char *TAG = "Agent";

// === AgentClient ===
AgentClient &AgentClient::GetInstance() { static AgentClient i; return i; }

// 向后兼容：通用初始化（所有端点用同一地址）
void AgentClient::Init(const char *url, const char *key, const char *model) {
    default_ep_.Set(url, key, model);
    ESP_LOGI(TAG, "Agent init (default): url=%s model=%s", url, model);
}

// 分别配置各端点
void AgentClient::SetChatEndpoint(const char *url, const char *api_key, const char *model) {
    chat_ep_.Set(url, api_key, model);
    ESP_LOGI(TAG, "Chat endpoint: %s [%s]", url, model);
}

void AgentClient::SetAsrEndpoint(const char *url, const char *api_key, const char *model) {
    asr_ep_.Set(url, api_key, model);
    ESP_LOGI(TAG, "ASR endpoint: %s [%s]", url, model);
}

void AgentClient::SetTtsEndpoint(const char *url, const char *api_key, const char *model) {
    tts_ep_.Set(url, api_key, model);
    ESP_LOGI(TAG, "TTS endpoint: %s [%s]", url, model);
}

void AgentClient::SetVisionEndpoint(const char *url, const char *api_key, const char *model) {
    vision_ep_.Set(url, api_key, model);
    ESP_LOGI(TAG, "Vision endpoint: %s [%s]", url, model);
}

// === ASR: POST /v1/audio/transcriptions ===
void AgentClient::Asr(const uint8_t *pcm_data, size_t pcm_len, int sample_rate) {
    auto &ep = GetAsrEp();
    ESP_LOGI(TAG, "ASR: %zu bytes @ %dHz → %s [%s]", pcm_len, sample_rate, ep.url, ep.model);
    busy_ = true;

    char url[256];
    snprintf(url, sizeof(url), "%s/audio/transcriptions", ep.url);

    // 构建 WAV（PCM 16bit mono → WAV header + data）
    size_t wav_len = 44 + pcm_len;
    uint8_t *wav = (uint8_t *)malloc(wav_len);
    if (!wav) { busy_ = false; return; }

    memcpy(wav, "RIFF", 4);
    uint32_t chunk_size = wav_len - 8;
    memcpy(wav + 4, &chunk_size, 4);
    memcpy(wav + 8, "WAVEfmt ", 8);
    uint32_t subchunk1_size = 16;
    memcpy(wav + 16, &subchunk1_size, 4);
    uint16_t audio_format = 1;
    memcpy(wav + 20, &audio_format, 2);
    uint16_t num_channels = 1;
    memcpy(wav + 22, &num_channels, 2);
    uint32_t sr = sample_rate;
    memcpy(wav + 24, &sr, 4);
    uint32_t byte_rate = sample_rate * 2;
    memcpy(wav + 28, &byte_rate, 4);
    uint16_t block_align = 2;
    memcpy(wav + 32, &block_align, 2);
    uint16_t bits_per_sample = 16;
    memcpy(wav + 34, &bits_per_sample, 2);
    memcpy(wav + 36, "data", 4);
    uint32_t data_size = pcm_len;
    memcpy(wav + 40, &data_size, 4);
    memcpy(wav + 44, pcm_data, pcm_len);

    esp_http_client_config_t cfg = {};
    cfg.url = url;
    cfg.method = HTTP_METHOD_POST;
    cfg.timeout_ms = 30000;

    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (ep.api_key[0]) {
        char hdr[128];
        snprintf(hdr, sizeof(hdr), "Bearer %s", ep.api_key);
        esp_http_client_set_header(client, "Authorization", hdr);
    }
    esp_http_client_set_header(client, "Content-Type", "audio/wav");
    esp_http_client_set_post_field(client, (const char *)wav, wav_len);

    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        int status = esp_http_client_get_status_code(client);
        int len = esp_http_client_get_content_length(client);
        if (len > 0) {
            std::string resp(len, '\0');
            esp_http_client_read(client, &resp[0], len);
            ESP_LOGI(TAG, "ASR [%d]: %s", status, resp.c_str());
            cJSON *json = cJSON_Parse(resp.c_str());
            if (json) {
                cJSON *text = cJSON_GetObjectItem(json, "text");
                if (text && cJSON_IsString(text) && cb_.on_asr) {
                    cb_.on_asr(text->valuestring);
                }
                cJSON_Delete(json);
            }
        }
    } else {
        ESP_LOGE(TAG, "ASR HTTP failed: %s", esp_err_to_name(err));
    }

    esp_http_client_cleanup(client);
    free(wav);
    busy_ = false;
}

// === Chat: POST /v1/chat/completions (SSE 流式) ===
void AgentClient::Chat(const AgentMessage *messages, int count) {
    auto &ep = GetChatEp();
    ESP_LOGI(TAG, "Chat: %d messages → %s [%s]", count, ep.url, ep.model);
    busy_ = true;

    char url[256];
    snprintf(url, sizeof(url), "%s/chat/completions", ep.url);

    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "model", ep.model);
    cJSON_AddBoolToObject(root, "stream", true);
    cJSON *msgs = cJSON_AddArrayToObject(root, "messages");
    for (int i = 0; i < count; i++) {
        cJSON *msg = cJSON_CreateObject();
        cJSON_AddStringToObject(msg, "role", messages[i].role);
        cJSON_AddStringToObject(msg, "content", messages[i].content);
        cJSON_AddItemToArray(msgs, msg);
    }
    char *json_str = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);

    esp_http_client_config_t cfg = {};
    cfg.url = url;
    cfg.method = HTTP_METHOD_POST;
    cfg.timeout_ms = 60000;

    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (ep.api_key[0]) {
        char hdr[128];
        snprintf(hdr, sizeof(hdr), "Bearer %s", ep.api_key);
        esp_http_client_set_header(client, "Authorization", hdr);
    }
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, json_str, strlen(json_str));

    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        int len = esp_http_client_get_content_length(client);
        if (len > 0) {
            std::string resp(len, '\0');
            esp_http_client_read(client, &resp[0], len);

            std::string full_text;
            size_t pos = 0;
            while (pos < resp.size()) {
                size_t line_start = resp.find("data: ", pos);
                if (line_start == std::string::npos) break;
                line_start += 6;
                size_t line_end = resp.find('\n', line_start);
                if (line_end == std::string::npos) line_end = resp.size();
                std::string line = resp.substr(line_start, line_end - line_start);
                pos = line_end + 1;
                if (line == "[DONE]") break;

                cJSON *chunk = cJSON_Parse(line.c_str());
                if (chunk) {
                    cJSON *choices = cJSON_GetObjectItem(chunk, "choices");
                    if (choices && cJSON_GetArraySize(choices) > 0) {
                        cJSON *choice = cJSON_GetArrayItem(choices, 0);
                        cJSON *delta = cJSON_GetObjectItem(choice, "delta");
                        if (delta) {
                            cJSON *content = cJSON_GetObjectItem(delta, "content");
                            if (content && cJSON_IsString(content)) {
                                full_text += content->valuestring;
                                if (cb_.on_llm_token) cb_.on_llm_token(content->valuestring);
                            }
                        }
                    }
                    cJSON_Delete(chunk);
                }
            }
            ESP_LOGI(TAG, "Chat reply: %s", full_text.c_str());
            if (cb_.on_llm_done) cb_.on_llm_done(full_text.c_str());
        }
    } else {
        ESP_LOGE(TAG, "Chat HTTP failed: %s", esp_err_to_name(err));
    }

    esp_http_client_cleanup(client);
    free(json_str);
    busy_ = false;
}

// === TTS: POST /v1/audio/speech ===
void AgentClient::Tts(const char *text) {
    auto &ep = GetTtsEp();
    ESP_LOGI(TAG, "TTS: %.50s... → %s [%s]", text, ep.url, ep.model);
    busy_ = true;

    char url[256];
    snprintf(url, sizeof(url), "%s/audio/speech", ep.url);

    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "model", ep.model);
    cJSON_AddStringToObject(root, "input", text);
    cJSON_AddStringToObject(root, "voice", "alloy");
    cJSON_AddStringToObject(root, "response_format", "pcm");
    cJSON_AddNumberToObject(root, "speed", 1.0);
    char *json_str = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);

    esp_http_client_config_t cfg = {};
    cfg.url = url;
    cfg.method = HTTP_METHOD_POST;
    cfg.timeout_ms = 30000;

    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (ep.api_key[0]) {
        char hdr[128];
        snprintf(hdr, sizeof(hdr), "Bearer %s", ep.api_key);
        esp_http_client_set_header(client, "Authorization", hdr);
    }
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, json_str, strlen(json_str));

    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        int len = esp_http_client_get_content_length(client);
        if (len > 0 && cb_.on_tts_audio) {
            size_t total = 0;
            size_t buf_size = len > 0 ? len : 32768;
            uint8_t *buf = (uint8_t *)malloc(buf_size);
            if (buf) {
                int read;
                while ((read = esp_http_client_read(client, (char *)buf + total, buf_size - total)) > 0) {
                    total += read;
                    if (total >= buf_size) break;
                }
                ESP_LOGI(TAG, "TTS audio: %zu bytes", total);
                if (total > 0) cb_.on_tts_audio(buf, total);
                free(buf);
            }
        }
    } else {
        ESP_LOGE(TAG, "TTS HTTP failed: %s", esp_err_to_name(err));
    }

    esp_http_client_cleanup(client);
    free(json_str);
    busy_ = false;
}

// === Vision（阶段二）===
void AgentClient::VisionQuery(const uint8_t *jpeg_data, size_t jpeg_len, const char *question) {
    auto &ep = GetVisionEp();
    ESP_LOGI(TAG, "Vision: %zu bytes → %s [%s]", jpeg_len, ep.url, ep.model);
    busy_ = true;
    // TODO: 阶段二 — 多模态 chat
    busy_ = false;
}

// === Motion（阶段三）===
void AgentClient::MotionCommand(const uint8_t *jpeg_data, size_t jpeg_len, const char *instruction) {
    ESP_LOGI(TAG, "Motion cmd: %s", instruction);
    busy_ = true;
    busy_ = false;
}

void AgentClient::MotionExecuteJson(const char *actions_json) {
    ESP_LOGI(TAG, "Execute JSON: %.50s...", actions_json);
}

// === WebServer ===
static const char *WS_TAG = "Web";
static httpd_handle_t s_httpd = nullptr;
static volatile bool s_dns_running = false;

// ---- Captive portal DNS server (responds all A queries with 192.168.4.1) ----
static void dns_server_task(void *arg) {
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        ESP_LOGE(WS_TAG, "DNS socket create failed");
        s_dns_running = false;
        vTaskDelete(NULL);
        return;
    }

    struct sockaddr_in server_addr = {};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(55553);
    server_addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        ESP_LOGE(WS_TAG, "DNS bind failed");
        close(sock);
        s_dns_running = false;
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(WS_TAG, "Captive portal DNS server started on port 55553");

    uint8_t buf[512];
    while (s_dns_running) {
        struct sockaddr_in client_addr = {};
        socklen_t addr_len = sizeof(client_addr);
        int len = recvfrom(sock, buf, sizeof(buf), 0, (struct sockaddr *)&client_addr, &addr_len);
        if (len < 12) continue;  // minimum DNS header size

        // Build DNS response: copy transaction ID + flags (QR=1, AA=1, RA=1)
        uint8_t resp[512];
        memcpy(resp, buf, 2);              // transaction ID
        resp[2] = 0x81; resp[3] = 0x80;    // flags: QR=1, RD=1
        resp[4] = 0x00; resp[5] = 0x01;    // questions: 1
        resp[6] = 0x00; resp[7] = 0x01;    // answers: 1
        resp[8] = 0x00; resp[9] = 0x00;    // authority: 0
        resp[10] = 0x00; resp[11] = 0x00;  // additional: 0

        // Copy the question section
        int qname_end = 12;
        while (qname_end < len && buf[qname_end] != 0) {
            qname_end += buf[qname_end] + 1;
        }
        qname_end++;  // skip the terminating 0
        int question_len = qname_end - 12 + 4; // name + type(2) + class(2)
        memcpy(resp + 12, buf + 12, question_len);
        int resp_len = 12 + question_len;

        // Answer section: pointer to name at offset 12
        resp[resp_len++] = 0xC0;
        resp[resp_len++] = 0x0C;  // name pointer
        resp[resp_len++] = 0x00; resp[resp_len++] = 0x01;  // type A
        resp[resp_len++] = 0x00; resp[resp_len++] = 0x01;  // class IN
        resp[resp_len++] = 0x00; resp[resp_len++] = 0x00;
        resp[resp_len++] = 0x00; resp[resp_len++] = 0x3C;  // TTL 60s
        resp[resp_len++] = 0x00; resp[resp_len++] = 0x04;  // rdlength 4
        resp[resp_len++] = 192; resp[resp_len++] = 168;
        resp[resp_len++] = 4;   resp[resp_len++] = 1;      // 192.168.4.1

        sendto(sock, resp, resp_len, 0, (struct sockaddr *)&client_addr, addr_len);
    }

    close(sock);
    ESP_LOGI(WS_TAG, "DNS server stopped");
    vTaskDelete(NULL);
}

// ---- embedded HTML config page (mobile-friendly, dark, Chinese) ----
static const char CONFIG_PAGE_HTML[] = R"rawliteral(<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>小希配置</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#1a1a2e;color:#e0e0e0;
  padding:1rem;max-width:480px;margin:auto}
h1{text-align:center;font-size:1.4rem;padding:.8rem 0;color:#7f8fff}
.section{background:#16213e;border-radius:10px;padding:1rem;margin-bottom:1rem}
.section h2{font-size:1rem;color:#7f8fff;margin-bottom:.6rem;border-bottom:1px solid #333;padding-bottom:.3rem}
label{display:block;font-size:.85rem;color:#aaa;margin-top:.5rem}
input[type=text],input[type=password],select{width:100%;padding:.5rem;border:1px solid #333;
  border-radius:6px;background:#0f3460;color:#e0e0e0;font-size:.9rem;margin-top:.2rem}
button{width:100%;padding:.7rem;margin-top:.8rem;border:none;border-radius:8px;
  background:#7f8fff;color:#fff;font-size:1rem;font-weight:700;cursor:pointer}
button:active{background:#5a6fd6}
#status{font-size:.8rem;color:#8f8;margin-top:.3rem}
#toast{position:fixed;top:1rem;left:50%;transform:translateX(-50%);
  background:#4caf50;color:#fff;padding:.5rem 1.2rem;border-radius:8px;
  display:none;font-size:.9rem;z-index:999}
.asr-fields,.tts-fields{margin-top:.4rem;padding:.4rem;border:1px dashed #333;border-radius:6px}
</style></head><body>
<h1>🤖 小希机器人配置</h1>

<!-- 状态 -->
<div class="section">
  <h2>📡 设备状态</h2>
  <div id="status">加载中...</div>
</div>

<!-- WiFi -->
<div class="section">
  <h2>📶 WiFi设置</h2>
  <label>SSID</label><input id="wssid" type="text" placeholder="WiFi名称">
  <label>密码</label><input id="wpwd" type="password" placeholder="WiFi密码">
  <div style="margin-top:.6rem;display:flex;align-items:center;justify-content:space-between">
    <span style="font-size:.85rem;color:#aaa">WiFi连上后保留AP热点</span>
    <div id="keepap-switch" onclick="toggleKeepAp()" style="position:relative;width:48px;height:26px;background:#333;border-radius:13px;cursor:pointer;transition:.3s">
      <div id="keepap-knob" style="position:absolute;top:2px;left:2px;width:22px;height:22px;background:#fff;border-radius:50%;transition:.3s"></div>
    </div>
  </div>
  <div style="font-size:.75rem;color:#666;margin-top:.2rem" id="keepap-label">开启</div>
</div>

<!-- Agent -->
<div class="section">
  <h2>🌐 代理服务器</h2>
  <label>Agent URL</label><input id="aurl" type="text" placeholder="http://192.168.1.11:8080/v1">
</div>

<!-- ASR -->
<div class="section">
  <h2>🎤 ASR方案选择</h2>
  <select id="asr_sel" onchange="toggleAsr()">
    <option value="mimo">小米mimo-v2-omni</option>
    <option value="funasr">小智FunASR</option>
    <option value="sensevoice">本地SenseVoice</option>
  </select>
  <div class="asr-fields">
    <label>ASR URL</label><input id="asr_url" type="text" placeholder="http://...">
    <label>API Key</label><input id="asr_key" type="text" placeholder="(可选)">
    <label>Model</label><input id="asr_model" type="text" placeholder="model name">
  </div>
</div>

<!-- TTS -->
<div class="section">
  <h2>🔊 TTS方案选择</h2>
  <select id="tts_sel" onchange="toggleTts()">
    <option value="mimo">小米mimo-v2.5-tts</option>
    <option value="edge">EdgeTTS</option>
    <option value="piper">本地Piper</option>
  </select>
  <div class="tts-fields">
    <label>TTS URL</label><input id="tts_url" type="text" placeholder="http://...">
    <label>API Key</label><input id="tts_key" type="text" placeholder="(可选)">
    <label>Model</label><input id="tts_model" type="text" placeholder="model name">
  </div>
</div>

<button onclick="saveCfg()">💾 保存配置</button>
<div id="toast">✅ 已保存，设备将重启...</div>

<script>
const ASR_PRESETS={
  mimo:{url:'https://api.mify.ai/v1',key:'',model:'mimo-v2-omni'},
  funasr:{url:'http://192.168.1.11:10095/v1',key:'',model:'paraformer-zh'},
  sensevoice:{url:'http://192.168.1.11:9000/v1',key:'',model:'SenseVoice'}
};
const TTS_PRESETS={
  mimo:{url:'https://api.mify.ai/v1',key:'',model:'mimo-v2.5-tts'},
  edge:{url:'http://192.168.1.11:10096/v1',key:'',model:'edge-tts'},
  piper:{url:'http://192.168.1.11:5000/v1',key:'',model:'piper'}
};
var keepApOn=true;
function setKeepApUI(on){
  keepApOn=on;
  document.getElementById('keepap-switch').style.background=on?'#7f8fff':'#333';
  document.getElementById('keepap-knob').style.left=on?'24px':'2px';
  document.getElementById('keepap-label').textContent=on?'开启':'关闭';
}
function toggleKeepAp(){setKeepApUI(!keepApOn);}
function toggleAsr(){let p=ASR_PRESETS[document.getElementById('asr_sel').value];
  document.getElementById('asr_url').value=p.url;
  document.getElementById('asr_key').value=p.key;
  document.getElementById('asr_model').value=p.model;}
function toggleTts(){let p=TTS_PRESETS[document.getElementById('tts_sel').value];
  document.getElementById('tts_url').value=p.url;
  document.getElementById('tts_key').value=p.key;
  document.getElementById('tts_model').value=p.model;}

// load current config
fetch('/api/config').then(r=>r.json()).then(c=>{
  document.getElementById('wssid').value=c.wifi_ssid||'';
  document.getElementById('wpwd').value=c.wifi_password||'';
  document.getElementById('aurl').value=c.agent_url||'';
  document.getElementById('asr_url').value=c.asr_url||'';
  document.getElementById('asr_key').value=c.asr_key||'';
  document.getElementById('asr_model').value=c.asr_model||'';
  document.getElementById('tts_url').value=c.tts_url||'';
  document.getElementById('tts_key').value=c.tts_key||'';
  document.getElementById('tts_model').value=c.tts_model||'';
  setKeepApUI(c.keep_ap_on_sta!==false);
}).catch(()=>{});

// load status
fetch('/api/status').then(r=>r.json()).then(s=>{
  document.getElementById('status').innerHTML=
    'WiFi: <b>'+(s.wifi_status||'unknown')+'</b><br>IP: <b>'+(s.ip||'0.0.0.0')+'</b>';
}).catch(()=>{});

function saveCfg(){
  let body={
    wifi_ssid:document.getElementById('wssid').value,
    wifi_password:document.getElementById('wpwd').value,
    agent_url:document.getElementById('aurl').value,
    asr_url:document.getElementById('asr_url').value,
    asr_key:document.getElementById('asr_key').value,
    asr_model:document.getElementById('asr_model').value,
    tts_url:document.getElementById('tts_url').value,
    tts_key:document.getElementById('tts_key').value,
    tts_model:document.getElementById('tts_model').value,
    keep_ap_on_sta:keepApOn
  };
  fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)}).then(r=>r.json()).then(j=>{
      let t=document.getElementById('toast');t.style.display='block';
      setTimeout(()=>t.style.display='none',3000);
  }).catch(e=>alert('保存失败:'+e));
}
</script></body></html>)rawliteral";

// ---- embedded HTML WiFi setup page (captive portal, mobile-friendly, dark) ----
static const char WIFI_SETUP_HTML[] = R"rawliteral(<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>📶 连接WiFi</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#1a1a2e;color:#e0e0e0;
  padding:1rem;max-width:480px;margin:auto;display:flex;flex-direction:column;
  min-height:100vh;justify-content:center}
.card{background:#16213e;border-radius:12px;padding:1.5rem;margin-bottom:1rem;
  box-shadow:0 4px 20px rgba(0,0,0,0.3)}
h1{text-align:center;font-size:1.5rem;padding:.5rem 0;color:#7f8fff}
.ap-name{text-align:center;font-size:.85rem;color:#aaa;margin-bottom:1rem}
label{display:block;font-size:.85rem;color:#aaa;margin-top:.7rem}
input[type=text],input[type=password]{width:100%;padding:.6rem;border:1px solid #333;
  border-radius:8px;background:#0f3460;color:#e0e0e0;font-size:1rem;margin-top:.2rem}
.pwd-wrap{position:relative}
.pwd-wrap input{padding-right:2.5rem}
.pwd-toggle{position:absolute;right:.6rem;top:50%;transform:translateY(-50%);
  background:none;border:none;color:#7f8fff;font-size:1.1rem;cursor:pointer}
button{width:100%;padding:.8rem;margin-top:1rem;border:none;border-radius:10px;
  background:#7f8fff;color:#fff;font-size:1.05rem;font-weight:700;cursor:pointer}
button:active{background:#5a6fd6}
#msg{text-align:center;margin-top:.8rem;font-size:.9rem;color:#7f8fff;display:none}
</style></head><body>
<div class="card">
  <h1>📶 连接WiFi</h1>
  <div class="ap-name">当前热点: <b>XiaoXi-Setup</b></div>
  <label>WiFi名称</label>
  <input id="ssid" type="text" placeholder="请输入WiFi名称">
  <label>WiFi密码</label>
  <div class="pwd-wrap">
    <input id="pwd" type="password" placeholder="请输入WiFi密码">
    <button class="pwd-toggle" type="button" onclick="togglePwd()">👁</button>
  </div>
  <button onclick="saveWifi()">保存并连接</button>
  <div id="msg"></div>
</div>
<script>
function togglePwd(){
  let i=document.getElementById('pwd');
  i.type=i.type==='password'?'text':'password';
}
function saveWifi(){
  let ssid=document.getElementById('ssid').value.trim();
  let pwd=document.getElementById('pwd').value;
  if(!ssid){alert('请输入WiFi名称');return;}
  let msg=document.getElementById('msg');
  msg.style.display='block';
  msg.textContent='正在连接...';
  fetch('/api/wifi',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ssid:ssid,password:pwd})
  }).then(r=>r.json()).then(j=>{
    msg.textContent='✅ 已保存，设备将自动重启连接WiFi...';
  }).catch(e=>{
    msg.textContent='❌ 保存失败: '+e;
  });
}
</script></body></html>)rawliteral";

// ---- HTTP handlers ----

static esp_err_t handle_root(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html; charset=utf-8");
    if (WifiManager::GetInstance().GetStatus() == WifiStatus::AP_MODE) {
        return httpd_resp_send(req, WIFI_SETUP_HTML, sizeof(WIFI_SETUP_HTML) - 1);
    }
    return httpd_resp_send(req, CONFIG_PAGE_HTML, sizeof(CONFIG_PAGE_HTML) - 1);
}

// ---- Captive portal: POST /api/wifi ----
static esp_err_t handle_post_wifi(httpd_req_t *req) {
    int total = req->content_len;
    if (total <= 0 || total > 512) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "bad request");
        return ESP_FAIL;
    }
    std::string body(total, '\0');
    int received = 0;
    while (received < total) {
        int ret = httpd_req_recv(req, &body[received], total - received);
        if (ret <= 0) { httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "recv"); return ESP_FAIL; }
        received += ret;
    }

    cJSON *root = cJSON_Parse(body.c_str());
    if (!root) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "invalid json");
        return ESP_FAIL;
    }

    XiaoXiConfig cfg = Config::GetInstance().Get();

    cJSON *j;
    if ((j = cJSON_GetObjectItem(root, "ssid")) && cJSON_IsString(j))
        strncpy(cfg.wifi_ssid, j->valuestring, sizeof(cfg.wifi_ssid) - 1);
    if ((j = cJSON_GetObjectItem(root, "password")) && cJSON_IsString(j))
        strncpy(cfg.wifi_password, j->valuestring, sizeof(cfg.wifi_password) - 1);

    cJSON_Delete(root);

    Config::GetInstance().Set(cfg);
    Config::GetInstance().Save();
    ESP_LOGI(WS_TAG, "WiFi config saved via captive portal — will restart in 2s");

    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, "{\"ok\":true}");

    vTaskDelay(pdMS_TO_TICKS(2000));
    esp_restart();
    return ESP_OK;
}

// ---- Captive portal: redirect handler for detection URLs ----
static esp_err_t handle_captive_redirect(httpd_req_t *req) {
    httpd_resp_set_status(req, "302 Found");
    httpd_resp_set_hdr(req, "Location", "http://192.168.4.1/");
    return httpd_resp_send(req, NULL, 0);
}

static esp_err_t handle_get_config(httpd_req_t *req) {
    auto &cfg = Config::GetInstance().Get();
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "wifi_ssid", cfg.wifi_ssid);
    cJSON_AddStringToObject(root, "wifi_password", cfg.wifi_password);
    cJSON_AddStringToObject(root, "agent_url", cfg.agent_url);
    cJSON_AddStringToObject(root, "asr_url", cfg.asr.url);
    cJSON_AddStringToObject(root, "asr_key", cfg.asr.api_key);
    cJSON_AddStringToObject(root, "asr_model", cfg.asr.model);
    cJSON_AddStringToObject(root, "tts_url", cfg.tts.url);
    cJSON_AddStringToObject(root, "tts_key", cfg.tts.api_key);
    cJSON_AddStringToObject(root, "tts_model", cfg.tts.model);
    cJSON_AddBoolToObject(root, "keep_ap_on_sta", cfg.keep_ap_on_sta);
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    httpd_resp_set_type(req, "application/json");
    esp_err_t ret = httpd_resp_send(req, out, strlen(out));
    free(out);
    return ret;
}

static esp_err_t handle_get_status(httpd_req_t *req) {
    auto &wm = WifiManager::GetInstance();
    const char *status_str = "disconnected";
    switch (wm.GetStatus()) {
        case WifiStatus::CONNECTED:   status_str = "connected"; break;
        case WifiStatus::CONNECTING:  status_str = "connecting"; break;
        case WifiStatus::AP_MODE:     status_str = "AP模式"; break;
        default: break;
    }
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "wifi_status", status_str);
    cJSON_AddStringToObject(root, "ip", wm.GetIP());
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    httpd_resp_set_type(req, "application/json");
    esp_err_t ret = httpd_resp_send(req, out, strlen(out));
    free(out);
    return ret;
}

static esp_err_t handle_post_config(httpd_req_t *req) {
    int total = req->content_len;
    if (total <= 0 || total > 2048) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "bad request");
        return ESP_FAIL;
    }
    std::string body(total, '\0');
    int received = 0;
    while (received < total) {
        int ret = httpd_req_recv(req, &body[received], total - received);
        if (ret <= 0) { httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "recv"); return ESP_FAIL; }
        received += ret;
    }

    cJSON *root = cJSON_Parse(body.c_str());
    if (!root) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "invalid json");
        return ESP_FAIL;
    }

    XiaoXiConfig cfg = Config::GetInstance().Get();

    // WiFi
    cJSON *j;
    if ((j = cJSON_GetObjectItem(root, "wifi_ssid")) && cJSON_IsString(j))
        strncpy(cfg.wifi_ssid, j->valuestring, sizeof(cfg.wifi_ssid) - 1);
    if ((j = cJSON_GetObjectItem(root, "wifi_password")) && cJSON_IsString(j))
        strncpy(cfg.wifi_password, j->valuestring, sizeof(cfg.wifi_password) - 1);
    // Agent
    if ((j = cJSON_GetObjectItem(root, "agent_url")) && cJSON_IsString(j))
        strncpy(cfg.agent_url, j->valuestring, sizeof(cfg.agent_url) - 1);
    // ASR
    if ((j = cJSON_GetObjectItem(root, "asr_url")) && cJSON_IsString(j))
        strncpy(cfg.asr.url, j->valuestring, sizeof(cfg.asr.url) - 1);
    if ((j = cJSON_GetObjectItem(root, "asr_key")) && cJSON_IsString(j))
        strncpy(cfg.asr.api_key, j->valuestring, sizeof(cfg.asr.api_key) - 1);
    if ((j = cJSON_GetObjectItem(root, "asr_model")) && cJSON_IsString(j))
        strncpy(cfg.asr.model, j->valuestring, sizeof(cfg.asr.model) - 1);
    // TTS
    if ((j = cJSON_GetObjectItem(root, "tts_url")) && cJSON_IsString(j))
        strncpy(cfg.tts.url, j->valuestring, sizeof(cfg.tts.url) - 1);
    if ((j = cJSON_GetObjectItem(root, "tts_key")) && cJSON_IsString(j))
        strncpy(cfg.tts.api_key, j->valuestring, sizeof(cfg.tts.api_key) - 1);
    if ((j = cJSON_GetObjectItem(root, "tts_model")) && cJSON_IsString(j))
        strncpy(cfg.tts.model, j->valuestring, sizeof(cfg.tts.model) - 1);
    // keep_ap_on_sta
    if ((j = cJSON_GetObjectItem(root, "keep_ap_on_sta")))
        cfg.keep_ap_on_sta = cJSON_IsTrue(j);

    cJSON_Delete(root);

    Config::GetInstance().Set(cfg);
    Config::GetInstance().Save();
    ESP_LOGI(WS_TAG, "Config saved — will restart in 2s");

    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, "{\"ok\":true}");

    // restart after response is sent
    vTaskDelay(pdMS_TO_TICKS(2000));
    esp_restart();
    return ESP_OK;
}

WebServer &WebServer::GetInstance() { static WebServer i; return i; }

void WebServer::Init() {
    ESP_LOGI(WS_TAG, "Web server init");
    // nothing to preload; HTML is a compile-time literal
}

void WebServer::Start() {
    if (running_) return;
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = 80;
    cfg.stack_size = 8192;
    cfg.max_uri_handlers = 16;

    if (httpd_start(&s_httpd, &cfg) != ESP_OK) {
        ESP_LOGE(WS_TAG, "httpd_start failed");
        return;
    }

    static const httpd_uri_t uris[] = {
        { .uri = "/",             .method = HTTP_GET,  .handler = handle_root,       .user_ctx = nullptr },
        { .uri = "/api/config",   .method = HTTP_GET,  .handler = handle_get_config, .user_ctx = nullptr },
        { .uri = "/api/config",   .method = HTTP_POST, .handler = handle_post_config,.user_ctx = nullptr },
        { .uri = "/api/status",   .method = HTTP_GET,  .handler = handle_get_status, .user_ctx = nullptr },
        { .uri = "/api/wifi",     .method = HTTP_POST, .handler = handle_post_wifi,  .user_ctx = nullptr },
        // Captive portal detection redirects
        { .uri = "/generate_204",        .method = HTTP_GET, .handler = handle_captive_redirect, .user_ctx = nullptr },
        { .uri = "/hotspot-detect.html", .method = HTTP_GET, .handler = handle_captive_redirect, .user_ctx = nullptr },
        { .uri = "/connecttest.txt",     .method = HTTP_GET, .handler = handle_captive_redirect, .user_ctx = nullptr },
        { .uri = "/ncsi.txt",            .method = HTTP_GET, .handler = handle_captive_redirect, .user_ctx = nullptr },
        { .uri = "/redirect",            .method = HTTP_GET, .handler = handle_captive_redirect, .user_ctx = nullptr },
    };
    for (auto &u : uris) httpd_register_uri_handler(s_httpd, &u);

    running_ = true;
    ESP_LOGI(WS_TAG, "Web server started on :80");
}

void WebServer::Stop() {
    // Stop DNS server if running
    if (s_dns_running) {
        s_dns_running = false;
        // Give DNS task time to exit
        vTaskDelay(pdMS_TO_TICKS(500));
        dns_task_ = nullptr;
    }
    if (s_httpd) {
        httpd_stop(s_httpd);
        s_httpd = nullptr;
    }
    running_ = false;
    ESP_LOGI(WS_TAG, "Web server stopped");
}

void WebServer::StartCaptivePortal() {
    // Start DNS server for captive portal
    if (!s_dns_running) {
        s_dns_running = true;
        xTaskCreate(dns_server_task, "dns_srv", 4096, nullptr, 5, &dns_task_);
    }
    // Start web server if not already running
    if (!running_) {
        Start();
    }
    ESP_LOGI(WS_TAG, "Captive portal active");
}
