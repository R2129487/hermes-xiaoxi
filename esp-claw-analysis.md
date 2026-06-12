# ESP-Claw 源码深度分析报告

> 分析时间：2026-06-10
> 源码路径：~/xiaoxi-project/esp-claw/
> 目标：深入了解 ESP-Claw 的 MCP 接口、LLM 配置、Lua 模块、IM 对接、事件路由、编译流程

---

## 目录

1. [MCP 接口详解](#1-mcp-接口详解)
2. [LLM 配置方式](#2-llm-配置方式)
3. [Lua 驱动模块](#3-lua-驱动模块)
4. [IM 平台对接](#4-im-平台对接)
5. [事件路由系统](#5-事件路由系统)
6. [编译和烧录流程](#6-编译和烧录流程)
7. [Hermes ↔ ESP-Claw 集成方案](#7-hermes--esp-claw-集成方案)

---

## 1. MCP 接口详解

### 1.1 架构概览

ESP-Claw 通过两个组件实现 MCP（Model Context Protocol）支持：

| 组件 | 源码位置 | 角色 |
|------|----------|------|
| `cap_mcp_client` | `components/claw_capabilities/cap_mcp_client/` | MCP 客户端，LLM 调用远程 MCP 服务器工具 |
| `cap_mcp_server` | `components/claw_capabilities/cap_mcp_server/` | MCP 服务端，将设备自身 Capability 暴露给外部 |

### 1.2 cap_mcp_client（客户端）

**注册的 LLM 工具（3个）：**

| 工具 ID | 说明 | 必填参数 |
|---------|------|----------|
| `mcp_list_tools` | 列出远程 MCP 服务器的可用工具 | `server_url` |
| `mcp_call_tool` | 调用远程 MCP 服务器上的指定工具 | `server_url`, `tool_name` |
| `mcp_discover` | 发现局域网内广播的 MCP 服务器 | 无（可选 `timeout_ms`, `include_self`） |

**工具参数详情：**

```json
// mcp_list_tools
{
  "server_url": "http://192.168.1.100:8080",  // 必填，MCP 服务器 URL
  "endpoint": "/mcp",                          // 可选，默认 MCP_MDNS_DEFAULT_ENDPOINT
  "cursor": "..."                              // 可选，分页游标
}

// mcp_call_tool
{
  "server_url": "http://192.168.1.100:8080",  // 必填
  "tool_name": "set_gpio",                     // 必填，工具名称
  "endpoint": "/mcp",                          // 可选
  "arguments": {"pin": 2, "level": 1}          // 可选，工具参数对象
}

// mcp_discover
{
  "timeout_ms": 3000,     // 可选，发现超时时间
  "include_self": true    // 可选，是否包含自身
}
```

**传输层实现细节：**
- 使用 `esp_mcp_mgr`（MCP Manager）管理 HTTP 客户端连接
- 默认 HTTP 超时：20000ms
- 缓冲区大小：4096 bytes
- 支持 HTTP keep-alive
- 每次调用创建临时 MCP Manager → 注册 endpoint → 执行请求 → 销毁
- 调用流程：`cap_mcp_mgr_create()` → `esp_mcp_mgr_post_tools_list/call()` → `cap_mcp_mgr_destroy()`

**Group 信息：**
- Group ID: `cap_mcp_client`
- 默认 LLM 可见：❌（需通过 Skill 激活）
- Kind: `CLAW_CAP_KIND_CALLABLE`

### 1.3 cap_mcp_server（服务端）

**核心功能：**
- 将设备已注册的 Capability 映射为 MCP 工具
- 支持 MCP SSE（Server-Sent Events）传输
- 通过 mDNS 广播，局域网可自动发现
- 完整生命周期管理：`init` → `add_tool` → `start` → `stop` → `deinit`

**注册自定义 MCP 工具的方式：**

```c
// 工具定义结构体
typedef struct {
    const char *name;                    // 工具名，如 "lua.list_scripts"
    const char *description;             // 工具描述
    esp_mcp_value_t (*callback)(const esp_mcp_property_list_t *properties);  // 回调函数
    const char *property_names[6];       // 参数名列表（最多6个）
    size_t property_count;               // 参数数量
} cap_mcp_server_tool_def_t;

// 使用示例
cap_mcp_server_tool_def_t my_tools[] = {
    {
        .name = "set_gpio",
        .description = "Set GPIO pin level",
        .callback = my_set_gpio_callback,
        .property_names = {"pin", "level"},
        .property_count = 2,
    },
};

// 初始化并注册
cap_mcp_server_init();
cap_mcp_server_add_tool(my_tools, sizeof(my_tools)/sizeof(my_tools[0]));
cap_mcp_server_start();
```

**HTTP 服务端配置：**
- 使用 `esp_http_server` 提供 HTTP 服务
- 端口：从 `mcp_mdns_config` 获取（默认由 mDNS 配置决定）
- 最大 URI 处理器：4
- 任务栈大小：8192 bytes
- 优先使用 PSRAM 分配任务栈

**mDNS 广播：**
- 服务名：`MCP_MDNS_DEFAULT_INSTANCE`
- 主机名：`MCP_MDNS_DEFAULT_HOSTNAME`
- Endpoint：`MCP_MDNS_DEFAULT_ENDPOINT`
- 启动后自动注册 mDNS 服务，局域网内其他设备可通过 `mcp_discover` 发现

**Group 信息：**
- Group ID: `cap_mcp_server`
- 默认 LLM 可见：❌
- Kind: `CLAW_CAP_KIND_HYBRID`（有生命周期管理）
- LLM 可调用工具数：0（作为服务端，不暴露 LLM 工具）

### 1.4 多设备 MCP 网络

`cap_mcp_client` + `cap_mcp_server` 配合使用时，多个 ESP-Claw 设备可组成分布式 Agent 网络：
- 设备 A 通过 `cap_mcp_server` 暴露自己的硬件控制能力
- 设备 B 的 LLM 通过 `mcp_discover` 发现设备 A，再通过 `mcp_call_tool` 调用其能力
- 全程通过局域网 MCP 协议通信，无需云端

---

## 2. LLM 配置方式

### 2.1 配置存储机制

ESP-Claw 使用 **NVS（Non-Volatile Storage）** 持久化配置：

- NVS 命名空间：`app`
- 优先级：**NVS 优先**，NVS 没有则用编译默认值
- 首次通过 Web 或串口保存后，以 NVS 为准
- 恢复出厂默认需清除 NVS 键

### 2.2 LLM 相关配置字段

| NVS 键 | 配置结构体字段 | 说明 | 默认值 |
|--------|---------------|------|--------|
| `llm_api_key` | `llm_api_key` | API 密钥 | 空 |
| `llm_backend` | `llm_backend_type` | 后端类型 | 空 |
| `llm_model` | `llm_model` | 模型名称 | 空 |
| `llm_base_url` | `llm_base_url` | API 基础 URL | 空 |
| `llm_auth_type` | `llm_auth_type` | 认证类型 | 空 |
| `llm_timeout_ms` | `llm_timeout_ms` | 请求超时 | `120000` |
| `llm_max_tokens` | `llm_max_tokens` | 最大 token 数 | `8192` |
| `llm_img_max_b` | `llm_default_image_max_bytes` | 图片最大字节数 | `524288` |
| `llm_max_toks_f` | `llm_max_tokens_field` | max_tokens 字段名 | 空 |
| `llm_sup_tools` | `llm_supports_tools` | 支持工具调用 | `false` |
| `llm_sup_vis` | `llm_supports_vision` | 支持视觉输入 | `false` |
| `llm_img_url_o` | `llm_image_remote_url_only` | 图片仅远程 URL | `false` |

### 2.3 支持的后端类型

ESP-Claw 支持两种 LLM API 后端：

| 后端类型 | 说明 | 对应 API |
|----------|------|----------|
| `openai_compatible` | OpenAI 兼容 API | `/chat/completions` |
| `anthropic_compatible` | Anthropic 兼容 API | `/messages` |

### 2.4 内置 LLM Provider 预设

源码中硬编码了以下预设（`s_legacy_llm_presets`）：

| Provider | backend_type | base_url | auth_type | max_tokens_field |
|----------|-------------|----------|-----------|-----------------|
| **OpenAI** | `openai_compatible` | `https://api.openai.com/v1` | `bearer` | `max_completion_tokens` |
| **Qwen（通义千问）** | `openai_compatible` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `bearer` | `max_tokens` |
| **DeepSeek** | `openai_compatible` | `https://api.deepseek.com` | `bearer` | `max_completion_tokens` |
| **Anthropic（Claude）** | `anthropic_compatible` | `https://api.anthropic.com/v1` | `none` | `max_tokens` |

### 2.5 自定义 LLM 配置（Base URL 格式）

通过 Web 配置页面的「LLM 设置」自定义：

**Base URL 规则：**
- 保留到版本号路径，不包含具体的 API 端点路径
- 不以 `/` 结尾

```
# OpenAI 格式
完整 URL: https://api.openai.com/v1/chat/completions
Base URL: https://api.openai.com/v1

# Anthropic 格式
完整 URL: https://api.anthropic.com/v1/messages
Base URL: https://api.anthropic.com/v1

# DeepSeek 格式
完整 URL: https://api.deepseek.com/chat/completions
Base URL: https://api.deepseek.com

# 自定义 OpenAI 兼容（如本地 Ollama）
Base URL: http://192.168.1.100:11434/v1
```

### 2.6 Web 配置页面

**访问方式：**
- 局域网：`http://esp-claw.local/` 或 `http://<设备IP>/`
- SoftAP 热点：SSID 为 `esp-claw-XXXXXX`，连接后访问上述地址
- 默认端口：80

**LLM 配置步骤：**
1. 打开 Web 控制台 → 系统设置 → LLM 设置
2. 选择内置供应商或自定义
3. 输入 API Key 和模型名称
4. 自定义时需填写 Base URL、选择 backend_type
5. 高级选项：支持视觉输入、支持工具调用、max_tokens 字段名等
6. 保存并重启生效

**⚠️ 重要提示：** 如果 API Key、backend_type、model 三项任一为空，`claw_core` 不会启动，整个推理核心不可用。

---

## 3. Lua 驱动模块

### 3.1 硬件驱动模块（lua_driver_*）

| 模块名 | 组件目录 | 功能说明 |
|--------|----------|----------|
| `adc` | `lua_driver_adc` | ADC 模数转换采样 |
| `gpio` | `lua_driver_gpio` | GPIO 读写、方向配置（input/output/input_output/output_od 等） |
| `i2c` | `lua_driver_i2c` | I2C 总线扫描与设备读写 |
| `ssd1306` | `lua_driver_i2c`（纯 Lua） | SSD1306 I2C OLED 显示屏驱动 |
| `lib_si12t_touch` | `lua_driver_i2c`（纯 Lua） | Si12T I2C 电容触摸驱动 |
| `mcpwm` | `lua_driver_mcpwm` | **通用 PWM 输出**（频率/占空比控制，可用于舵机/电机） |
| `pcnt` | `lua_driver_pcnt` | PCNT 脉冲计数器/编码器读取 |
| `touch` | `lua_driver_touch` | 电容触摸按键数据读取 |
| `uart` | `lua_driver_uart` | UART 串口收发（polling 读写） |

### 3.2 高层功能模块（lua_module_*）

| 模块名 | 组件目录 | 功能说明 |
|--------|----------|----------|
| `audio` | `lua_module_audio` | **音频播放/录制**（PCM/WAV）与频谱分析 |
| `ble_hid` | `lua_module_ble_hid` | BLE HID 复合外设（媒体控制、键盘、鼠标） |
| `board_manager` | `lua_module_board_manager` | 板级初始化与外设句柄获取 |
| `button` | `lua_module_button` | 按键事件注册与回调 |
| `capability` | `lua_module_call_capability` | 从 Lua 脚本直接调用已注册 Capability |
| `camera` | `lua_module_camera` | **摄像头拍照与流式采集** |
| `delay` | `lua_module_delay` | 毫秒级延时 `delay.delay_ms(n)` |
| `dht` | `lua_module_dht` | DHT 系列温湿度传感器读取 |
| `display` | `lua_module_display` | **LCD 屏幕绘图**（文字、图形、JPEG/PNG） |
| `environmental_sensor` | `lua_module_environmental_sensor` | BME690 温湿度、气压与气体数据读取 |
| `event_publisher` | `lua_module_event_publisher` | 从 Lua 脚本向 Event Router 发布事件 |
| `http_server` | `lua_module_http_server` | 在现有 HTTP 服务器上发布静态文件与 HTTP 回调 |
| `image` | `lua_module_image` | 通用图像帧类型、格式转换、缩放与文件读写 |
| `json` | `lua_module_json` | JSON 编码/解码辅助库 |
| `lib_fuel_gauge` | `lua_module_fuel_gauge`（纯 Lua） | 电池电量计库，支持 BQ27220/MAX17048 |
| `imu` | `lua_module_imu` | IMU 加速度计与陀螺仪数据读取 |
| `ir` | `lua_module_ir` | **红外接收、学习与发送** |
| `knob` | `lua_module_knob` | 旋钮/旋转编码器事件读取 |
| `lcd` | `lua_module_lcd` | LCD 面板初始化、背光与显示辅助控制 |
| `lcd_touch` | `lua_module_lcd_touch` | 触摸屏坐标读取 |
| `led_strip` | `lua_module_led_strip` | **WS2812 等可寻址 LED 灯带控制** |
| `lvgl` | `lua_module_lvgl` | LVGL 图形库绑定，支持完整 UI 控件与事件系统 |
| `magnetometer` | `lua_module_magnetometer` | 磁力计/指南针数据读取 |
| `motion_detect` | `lua_module_vision` | 基于 image.frame 的运动检测 |
| `sci` | `lua_module_sci` | DFRobot SCI 采集模块（DFR0999）I2C 读取 |
| `storage` | `lua_module_storage` | 文件系统操作 |
| `system` | `lua_module_system` | 时间、运行时长、IP、内存、堆、任务栈与 Wi-Fi 状态查询 |
| `thread` | `lua_module_thread` | Lua 任务管理、命名同步队列/信号量/事件组 |
| `arg_schema` | `lua_module_system`（纯 Lua） | 参数归一化辅助库 |

### 3.3 硬件控制相关模块重点

#### GPIO 控制
```lua
local gpio = require("gpio")
gpio.set_direction(2, "output")      -- 设置方向
gpio.set_level(2, 1)                 -- 输出高电平
local level = gpio.get_level(2)      -- 读取电平
-- mode: "input", "output", "input_output", "output_od", "input_output_od", "disable"
```

#### PWM / 舵机控制（MCPWM）
```lua
local mcpwm = require("mcpwm")
-- MCPWM 可控制频率和占空比，适用于舵机和电机
```

#### 摄像头
```lua
local camera = require("camera")
-- 拍照与流式采集
```

#### 音频
```lua
local audio = require("audio")
-- PCM/WAV 播放与录制，频谱分析
```

#### LED 灯带
```lua
local led_strip = require("led_strip")
-- WS2812 等可寻址 LED 控制
```

#### 红外遥控
```lua
local ir = require("ir")
-- 红外接收、学习与发送
```

#### LCD 显示
```lua
local display = require("display")
-- 文字、图形、JPEG/PNG 绘图，有独占所有权管理
```

### 3.4 模块注册机制

```c
// 注册函数命名：lua_module_<name>_register() 或 lua_driver_<name>_register()
esp_err_t lua_module_gpio_register(void) {
    return cap_lua_register_module("gpio", luaopen_gpio);
}

// 应用初始化阶段调用（必须在 cap_lua_register_group() 之前）
lua_module_gpio_register();
lua_module_audio_register();
lua_driver_mcpwm_register();
// ... 其他模块 ...
cap_lua_register_group("/fatfs/scripts");  // 锁定后不能再注册
```

### 3.5 从 Lua 调用 Capability

```lua
local cap = require("capability")
-- 可从 Lua 脚本直接调用已注册的 Capability 工具
```

### 3.6 向 Event Router 发布事件

```lua
local ep = require("event_publisher")
-- 简洁形式
ep.publish_message("Button pressed!")

-- 完整形式
ep.publish_message({
  source_cap = "lua_script",
  channel = args.channel,
  chat_id = args.chat_id,
  text = "Button pressed!",
})
```

---

## 4. IM 平台对接

### 4.1 架构

ESP-Claw 通过 `cap_im_platform` 组件统一管理所有 IM 平台。虽然源码统一在一个组件中，但运行时仍按平台拆分 Group。

### 4.2 支持的平台

| 平台 | 运行时 Group | 事件源 | 入站模型 | 支持的功能 |
|------|-------------|--------|----------|-----------|
| **微信** | `cap_im_wechat` | `wechat_gateway` | ClawBot 轮询 API | 文本、图片发送（不支持通用文件） |
| **QQ** | `cap_im_qq` | `qq_gateway` | QQ Bot WebSocket API | 文本、图片、文件发送 |
| **飞书** | `cap_im_feishu` | `feishu_gateway` | WebSocket/Event API | 文本（Markdown 卡片）、图片、文件发送 |
| **Telegram** | `cap_im_tg` | `tg_gateway` | Bot API 长轮询 | 文本、图片、文件发送，自动分片 |
| **Web（本地）** | `cap_im_local` | `local_gateway` | HTTP/WebSocket | 文本发送 |

### 4.3 微信对接

**配置参数（NVS）：**
| NVS 键 | 字段 | 说明 | 默认值 |
|--------|------|------|--------|
| `wechat_token` | `wechat_token` | 微信 Token（扫码生成） | 空 |
| `wechat_base_url` | `wechat_base_url` | 微信 API Base URL | `https://ilinkai.weixin.qq.com` |
| `wechat_cdn_url` | `wechat_cdn_base_url` | CDN Base URL | `https://novac2c.cdn.weixin.qq.com/c2c` |
| `wechat_acct_id` | `wechat_account_id` | 账号 ID | `default` |

**配置方式：**
1. Web 控制台 → 系统设置 → IM 设置 → 微信
2. 点击「生成二维码」按钮
3. 使用微信「扫一扫」扫描二维码完成配置
4. 保存并重启生效

**运行时工具：**
- `wechat_send_message` — 发送文本消息
- `wechat_send_image` — 发送图片
- 不支持通用文件发送

### 4.4 QQ 对接

**配置参数（NVS）：**
| NVS 键 | 字段 | 说明 |
|--------|------|------|
| `qq_app_id` | `qq_app_id` | QQ 机器人 App ID |
| `qq_app_secret` | `qq_app_secret` | QQ 机器人 App Secret |
| `qq_msg_type` | `qq_msg_type` | 消息类型（默认 `0`） |

**配置方式：**
1. 在 [QQ开放平台](https://q.qq.com/qqbot/openclaw/login.html) 创建 QQ 机器人
2. 获取 App ID 和 App Secret
3. Web 控制台 → IM 设置 → QQ → 填入凭证
4. 保存并重启

**运行时工具：**
- `qq_send_message` — 发送文本
- `qq_send_image` — 发送图片
- `qq_send_file` — 发送文件

**会话目标格式：**
- 私聊：`c2c:<openid>`
- 群聊：`group:<group_openid>`

### 4.5 飞书对接

**配置参数（NVS）：**
| NVS 键 | 字段 | 说明 |
|--------|------|------|
| `feishu_app_id` | `feishu_app_id` | 飞书应用 App ID |
| `feishu_secret` | `feishu_app_secret` | 飞书应用 App Secret |

**配置方式：**
1. 在 [飞书开放平台](https://open.feishu.cn/page/launcher?from=backend_oneclick) 创建飞书智能体应用
2. 获取 App ID 和 App Secret
3. Web 控制台 → IM 设置 → 飞书 → 填入凭证
4. 保存并重启

**⚠️ 注意：暂不支持 Lark 飞书国际版。**

**运行时工具：**
- `feishu_send_message` — 发送文本（优先使用 Markdown 交互卡片，失败回退纯文本）
- `feishu_send_image` — 发送图片
- `feishu_send_file` — 发送文件

### 4.6 Telegram 对接

**配置参数（NVS）：**
| NVS 键 | 字段 | 说明 |
|--------|------|------|
| `tg_bot_token` | `tg_bot_token` | Telegram Bot Token |

**配置方式：**
1. 在 Telegram 中与 [@botfather](https://t.me/botfather) 对话
2. 创建机器人并获取 Bot Token
3. Web 控制台 → IM 设置 → Telegram → 填入 Token
4. 保存并重启

**运行时工具：**
- `tg_send_message` — 发送文本（超长自动分片）
- `tg_send_image` — 发送图片（multipart 流式上传）
- `tg_send_file` — 发送文件

**内部实现细节：**
- 长轮询：`getUpdates`，20 秒超时
- 去重：FNV-1a 哈希缓存（64 条）
- 附件下载：异步队列 + 流式写入 FATFS
- 最大入站文件：2 MB

### 4.7 出站通道绑定

`edge_agent` 启动时自动绑定：
- `qq` → QQ 发送工具
- `feishu` → 飞书发送工具
- `telegram` → Telegram 发送工具
- `wechat` → 微信发送工具
- `web` → 本地 IM 发送工具

---

## 5. 事件路由系统

### 5.1 核心概念

ESP-Claw 是**事件驱动**架构，`claw_event_router` 是事件调度中枢。

**事件（Event）结构体 `claw_event_t` 包含：**
- Event ID、来源、目标
- Event 类型（message / out_message / trigger / schedule / attachment_saved / agent_stage）
- 聊天 ID、发送者
- 文本或 JSON Payload
- 时间戳、Session 策略

### 5.2 路由规则文件

规则存储在 `router_rules.json`（DATA 根目录下的 `router_rules/router_rules.json`）。

**规则 JSON 结构：**
```json
[
  {
    "id": "rule_id",                    // 必填，唯一标识
    "description": "规则描述",            // 可选
    "enabled": true,                     // 可选，默认 true
    "consume_on_match": true,            // 可选，命中后是否阻止继续匹配
    "ack": "确认消息模板",                // 可选
    "vars": {},                          // 可选，规则级局部变量
    "match": {                           // 必填，匹配条件
      "event_type": "message",           // 必填
      "event_key": "text",              // 可选
      "source_cap": "qq_gateway",       // 可选
      "source_channel": "qq",           // 可选
      "chat_id": "123456",              // 可选
      "content_type": "text",           // 可选
      "text": "/run",                   // 可选，精确匹配或前缀匹配
      "text_match_rule": "prefix"       // 可选：exact（默认）或 prefix
    },
    "actions": [                         // 必填，动作列表
      {
        "type": "run_agent",            // 动作类型
        "caller": "system",             // 可选：system/agent/console
        "input": {}                     // 动作参数
      }
    ]
  }
]
```

### 5.3 动作类型详解

| 动作类型 | 说明 | input 参数 |
|----------|------|-----------|
| `call_cap` | 直接执行 Capability（不经 LLM） | `cap`: capability 名称 |
| `run_agent` | 异步提交给 claw_core（LLM 推理） | `text`, `target_channel`, `target_chat_id`, `session_policy` |
| `run_script` | 运行 Lua 脚本 | `path`: 脚本路径, `async`: 是否异步 |
| `send_message` | 发送 IM 消息 | `channel`, `chat_id`, `message` |
| `emit_event` | 生成新事件 | `source_cap`, `event_type`, `text`, `payload_json`, `session_policy` |
| `drop` | 丢弃事件 | 无 |

### 5.4 模板变量

在 action 的 `input` 中可使用模板变量：
- `{{event.text}}` — 事件文本
- `{{event.source_channel}}` — 来源通道
- `{{event.chat_id}}` — 聊天 ID
- `{{match.text}}` — 匹配的文本
- `{{match.rule}}` — 匹配的规则文本
- `{{match.remainder}}` — prefix 模式下的剩余文本

### 5.5 会话策略

| 策略 | Session ID 格式 | 说明 |
|------|----------------|------|
| `chat` | `source_channel:chat_id` | 同一聊天窗口共享会话 |
| `trigger` | `trigger:source_cap:event_key` | 每类触发源独立会话 |
| `global` | `global:source_cap` | 同一来源 cap 共享全局会话 |
| `ephemeral` | `ephemeral:event_id` | 每个事件独立的一次性会话 |
| `nosave` | 空（长度为 0） | 不保存会话历史 |

### 5.6 工作流程

```
Event 入队 → 从队列取出 → 检查是否来自 event_router（防自循环）
    → 构建 ctx → 遍历规则集：
        → 规则已启用 && 所有 match 字段命中？
            → 是：依次执行 actions
                → consume_on_match = true？→ 停止匹配（Event 已消耗）
                → consume_on_match = false？→ 继续下一条规则
            → 否：继续下一条规则
    → 遍历完毕，未命中任何规则？
        → default_route_messages_to_agent && event_type = "message"？
            → 是：提交给默认 Agent
            → 否：处理完成
```

### 5.7 默认路由规则示例

```json
// Agent 输出消息发回 IM
{
  "id": "agent_out_message_send_message",
  "consume_on_match": true,
  "match": {
    "source_cap": "claw_core",
    "event_type": "out_message",
    "content_type": "text"
  },
  "actions": [
    {
      "type": "send_message",
      "input": {
        "channel": "{{event.source_channel}}",
        "chat_id": "{{event.chat_id}}",
        "message": "{{event.text}}"
      }
    }
  ]
}
```

### 5.8 定时调度

`cap_scheduler` 支持三种调度类型：
- `once` — 一次性
- `interval` — 间隔重复
- `cron` — 日历表达式（5 段，不含秒）

**LLM 工具：** `scheduler_list`, `scheduler_get`, `scheduler_add`, `scheduler_update`, `scheduler_remove`, `scheduler_enable`, `scheduler_disable`, `scheduler_pause`, `scheduler_resume`, `scheduler_trigger_now`, `scheduler_reload`

### 5.9 路由管理 LLM 工具

`cap_router_mgr` 提供：`list_router_rules`, `get_router_rule`, `add_router_rule`, `update_router_rule`, `delete_router_rule`, `reload_router_rules`

### 5.10 Console 命令

```sh
auto reload                  # 重新载入 router_rules.json
auto rules                   # 列出当前规则集
auto rule <id>               # 查看单条规则
auto add_rule '<json>'       # 新增规则
auto update_rule '<json>'    # 更新规则
auto delete_rule <id>        # 删除规则
auto emit_message <source_cap> <channel> <chat_id> <text>
auto emit_trigger <source_cap> <event_type> <event_key> '<payload_json>'
auto last                    # 查看最近一次匹配统计
```

---

## 6. 编译和烧录流程

### 6.1 环境要求

| 项目 | 要求 |
|------|------|
| **ESP-IDF 版本** | v5.5.4 |
| **额外工具** | `esp-bmgr-assist`（ESP Board Manager） |
| **操作系统** | Linux / macOS / Windows (WSL) |

### 6.2 支持的开发板

ESP-Claw 通过 ESP Board Manager 适配多种开发板，已支持：

**Espressif 官方：**
- `esp32_S3_DevKitC_1` — ESP32-S3 开发板（推荐入门）
- `esp32_S3_DevKitC_1_breadboard` — 面包板方案
- `esp_box_3` — ESP-BOX-3
- `esp_sparkbot` — SparkBot
- `esp_Ditto` — Ditto
- `esp_vocat_board_v1_2` — VOCAT 板
- `esp_SensairShuttle` — Sensair Shuttle
- `esp32_s31_korvo1` — ESP32-S31 Korvo1
- `esp32_p4_function_ev` — ESP32-P4 Function EV
- `esp32_p4_eye` — ESP32-P4 Eye

**第三方：**
- M5Stack: `m5stack_cores3`, `m5stack_sticks3`, `m5stack_tab5`
- DFRobot: `dfrobot_k10`, `dfrobot_romeo_ESP32_S3`, `dfrobot_firebeetle_2_*`, `dfrobot_ai_camera`
- Waveshare: `waveshare_ESP32_S3_RLCD_4_2`, `waveshare_esp32_s3_geek`, `waveshare_esp32_p4_nano`
- LilyGo: `lilygo_t_display_s3`, `lilygo_t_display_p4_v1`
- MoveCall: `movecall_moji_esp32s3`, `movecall_moji2_esp32c5`, `movecall_cuican_esp32s3`
- 其他: `xingzhi_395`, `nm_cyd_c5`

**支持的芯片：** ESP32-S3, ESP32-P4, ESP32-C5, ESP32-S31

### 6.3 编译步骤

```bash
# 1. 安装 ESP-IDF v5.5.4 并激活环境
. $IDF_PATH/export.sh

# 2. 安装 Board Manager
pip install esp-bmgr-assist

# 3. 获取源码
git clone https://github.com/espressif/esp-claw.git
cd esp-claw/application/edge_agent

# 4. 选择开发板（自动选择芯片型号，无需 set-target）
idf.py bmgr -c ./boards -b esp32_S3_DevKitC_1

# 5. 可选：调整 menuconfig
idf.py menuconfig
# - (Top) → App Claw Config：基础设置
# - (Top) → Component config → ESP-Claw Core → Agent stage notification verbosity
# - (Top) → Component config → ESP System Settings → Channel for console output

# 6. 编译
idf.py build

# 7. 烧录并监控
idf.py flash monitor
```

### 6.4 列出支持的开发板

```bash
idf.py bmgr -c ./boards -l
```

### 6.5 关键 Kconfig 选项

| 选项 | 说明 |
|------|------|
| `APP_CLAW_MEMORY_MODE` | 记忆模式：Structured（完整结构化，默认）/ Lightweight（轻量） |
| `APP_CLAW_ENABLE_EMOTE` | 是否启用 LCD 表情显示（仅带 LCD 的板有意义） |
| Agent stage notification verbosity | Simple（默认）/ Verbose（发布 agent_stage 事件） |

### 6.6 文件系统布局

- `/system`（只读）：固件内置 Skill、Lua 脚本、板级图像覆盖、恢复种子
- `/fatfs`（可写，DATA 根目录）：用户 Skill、路由规则、记忆、会话、收件箱

---

## 7. Hermes ↔ ESP-Claw 集成方案

### 7.1 方案概述

将 ESP-Claw 用作「动作引擎」，Hermes 智能体通过 MCP 协议控制 ESP32 硬件。

```
用户 → Hermes Agent → MCP Client → [局域网] → ESP-Claw MCP Server → 硬件控制
```

### 7.2 ESP-Claw 端配置

1. **确保 `cap_mcp_server` 已启用**
   - Web 控制台 → Capabilities 管理 → 确认 `cap_mcp_server` 已启用

2. **注册硬件控制工具**
   ESP-Claw 启动时会自动将已注册的 Capability 暴露为 MCP 工具
   - 可通过 Lua 脚本扩展自定义硬件控制逻辑
   - 可通过 `cap_mcp_server_add_tool()` 注册自定义 C 回调

3. **mDNS 广播**
   MCP Server 启动后自动通过 mDNS 广播，Hermes 端可自动发现

### 7.3 Hermes 端集成

Hermes 可以通过以下方式与 ESP-Claw 交互：

**方式 A：直接调用 MCP 工具**
```
Hermes MCP Client → HTTP POST → ESP-Claw MCP Server
1. mcp_discover → 发现局域网 ESP-Claw 设备
2. mcp_list_tools → 获取设备可用工具列表
3. mcp_call_tool → 调用具体工具（如 GPIO 控制、Lua 脚本执行等）
```

**方式 B：通过 Event Router 间接触发**
```
Hermes → HTTP 请求 → ESP-Claw HTTP API → Event Router → 规则匹配 → 硬件动作
```

### 7.4 可用的硬件控制能力

通过 MCP 协议，Hermes 可以间接利用 ESP-Claw 的所有能力：

| 能力 | MCP 工具 | 说明 |
|------|----------|------|
| Lua 脚本执行 | `lua_run_script` / `lua_run_script_async` | 运行任意 Lua 脚本控制硬件 |
| 文件管理 | `write_file` / `read_file` / `list_dir` | 管理设备文件系统 |
| 定时任务 | `scheduler_add` / `scheduler_list` 等 | 创建定时硬件控制任务 |
| 路由规则 | `add_router_rule` 等 | 配置自动化规则 |
| HTTP 请求 | `http_request` | 发起网络请求 |
| 系统信息 | `system_*` | 查询设备状态 |

### 7.5 典型用例

```lua
-- ESP-Claw 端 Lua 脚本：GPIO 控制
local gpio = require("gpio")
gpio.set_direction(2, "output")
gpio.set_level(2, 1)  -- 点亮 LED

-- ESP-Claw 端 Lua 脚本：舵机控制
local mcpwm = require("mcpwm")
-- 配置 PWM 控制舵机角度

-- Hermes 端通过 MCP 调用：
-- mcp_call_tool(server_url="http://esp-claw.local:8080", 
--               tool_name="lua_run_script",
--               arguments={script="set_gpio(2, 1)"})
```

---

## 附录：关键源码文件索引

| 文件 | 说明 |
|------|------|
| `components/claw_capabilities/cap_mcp_client/src/cap_mcp_client.c` | MCP 客户端 Capability 注册 |
| `components/claw_capabilities/cap_mcp_client/src/cap_mcp_client_core.c` | MCP 客户端 HTTP 通信核心 |
| `components/claw_capabilities/cap_mcp_client/src/cap_mcp_discover_core.c` | mDNS 发现实现 |
| `components/claw_capabilities/cap_mcp_server/src/cap_mcp_server.c` | MCP 服务端实现 |
| `components/claw_capabilities/cap_mcp_server/include/cap_mcp_server.h` | MCP 服务端 API |
| `components/claw_capabilities/cap_im_platform/src/cap_im_platform.c` | IM 平台统一入口 |
| `components/claw_capabilities/cap_im_platform/src/cap_im_wechat.c` | 微信后端 |
| `components/claw_capabilities/cap_im_platform/src/cap_im_qq.c` | QQ 后端 |
| `components/claw_capabilities/cap_im_platform/src/cap_im_feishu.c` | 飞书后端 |
| `components/claw_capabilities/cap_im_platform/src/cap_im_tg.c` | Telegram 后端 |
| `components/claw_modules/claw_event_router/include/claw_event_router.h` | Event Router API |
| `components/claw_modules/claw_event_router/include/claw_event.h` | 事件结构体定义 |
| `components/claw_modules/claw_event_router/include/claw_event_publisher.h` | 事件发布 API |
| `application/edge_agent/components/app_config/app_config.c` | 配置管理（含 LLM 预设） |
| `application/edge_agent/components/app_config/include/app_config.h` | 配置结构体定义 |
| `application/edge_agent/main/main.c` | 主入口 |
| `components/lua_modules/` | 所有 Lua 模块 |
| `docs/src/content/docs/zh-cn/` | 中文文档 |
