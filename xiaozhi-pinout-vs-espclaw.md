# 小智固件引脚定义 vs ESP-Claw 对照表

> 源码路径：~/xiaozhi-esp32/
> 更新时间：2026-06-10

---

## 你的板子：bread-compact-wifi（面包板方案）

从照片看：ESP32-S3-N16R8 + I2C OLED 屏幕（GND/VCC/SCK/SDA）

### 音频引脚（INMP441 麦克风 + MAX98357A 喇叭）

| 功能 | GPIO | 说明 |
|------|------|------|
| 麦克风 WS | GPIO_4 | I2S Word Select |
| 麦克风 SCK | GPIO_5 | I2S Serial Clock |
| 麦克风 DIN | GPIO_6 | I2S Data In |
| 喇叭 DOUT | GPIO_7 | I2S Data Out |
| 喇叭 BCLK | GPIO_15 | I2S Bit Clock |
| 喇叭 LRCK | GPIO_16 | I2S Left/Right Clock |

- 麦克风采样率：16000 Hz
- 喇叭采样率：24000 Hz
- 模式：Simplex（非全双工，收发分开）

### 屏幕引脚（SSD1306/SH1106 OLED，I2C）

| 功能 | GPIO | 说明 |
|------|------|------|
| SDA | GPIO_41 | I2C 数据线 |
| SCL | GPIO_42 | I2C 时钟线 |

- 分辨率：128×64（SSD1306 或 SH1106）
- 镜像：X/Y 都镜像

### 按钮/LED

| 功能 | GPIO | 说明 |
|------|------|------|
| RGB LED | GPIO_48 | 板载 RGB LED |
| BOOT 按钮 | GPIO_0 | 启动/配置按钮 |
| 触摸按钮 | GPIO_47 | 触摸感应 |
| 音量+ | GPIO_40 | 音量增加 |
| 音量- | GPIO_39 | 音量减少 |
| 外接灯/继电器 | GPIO_18 | LAMP 控制 |

---

## 其他常用板子引脚速查

### bread-compact-wifi-lcd（SPI LCD 版）

音频引脚同上（GPIO 4/5/6/7/15/16）

| 功能 | GPIO | 说明 |
|------|------|------|
| LCD 背光 | GPIO_42 | SPI LCD 背光 |
| LCD MOSI | GPIO_47 | SPI 数据 |
| LCD CLK | GPIO_21 | SPI 时钟 |
| LCD DC | GPIO_40 | 数据/命令 |
| LCD RST | GPIO_45 | 复位 |
| LCD CS | GPIO_41 | 片选 |

### esp-box-3（乐鑫官方 BOX3）

| 功能 | GPIO | 说明 |
|------|------|------|
| I2S MCLK | GPIO_2 | 主时钟 |
| I2S WS | GPIO_45 | Word Select |
| I2S BCLK | GPIO_17 | Bit Clock |
| I2S DIN | GPIO_16 | 麦克风数据 |
| I2S DOUT | GPIO_15 | 喇叭数据 |
| PA 使能 | GPIO_46 | 功放开关 |
| I2C SDA | GPIO_8 | 编解码器 I2C |
| I2C SCL | GPIO_18 | 编解码器 I2C |
| LCD 背光 | GPIO_47 | 屏幕背光 |

- 音频芯片：ES8311 DAC + ES7210 ADC
- 采样率：24000/24000 Hz

### doit-s3-aibox

| 功能 | GPIO | 说明 |
|------|------|------|
| 麦克风 WS | GPIO_41 | |
| 麦克风 SCK | GPIO_40 | |
| 麦克风 DIN | GPIO_42 | |
| 喇叭 DOUT | GPIO_18 | |
| 喇叭 BCLK | GPIO_17 | |
| 喇叭 LRCK | GPIO_16 | |
| RGB LED | GPIO_45 | |
| 音量+ | GPIO_15 | |
| 音量- | GPIO_9 | |

---

## ESP-Claw 板级配置对照

ESP-Claw 的板级配置在 YAML 文件中，格式不同但引脚可以对应：

### 小智 bread-compact-wifi → ESP-Claw 等价配置

```yaml
# 对应 ESP-Claw 的 board_peripherals.yaml
peripherals:
  - name: i2s_audio_in
    type: i2s
    role: rx
    config:
      gpio_num: 6       # DIN
      # WS=4, SCK=5 需要在 I2S config 中指定

  - name: i2s_audio_out
    type: i2s
    role: tx
    config:
      gpio_num: 7       # DOUT
      # BCLK=15, LRCK=16 需要在 I2S config 中指定

  - name: i2c_master     # OLED 屏幕
    type: i2c
    config:
      sda_pin: 41
      scl_pin: 42

  - name: rmt_tx         # RGB LED
    type: rmt
    role: tx
    config:
      gpio_num: 48

  - name: gpio_led       # 外接灯
    type: gpio
    config:
      gpio_num: 18
```

### 关键差异

| 项目 | 小智固件 | ESP-Claw |
|------|---------|----------|
| 配置格式 | C 头文件 `#define` | YAML + NVS |
| 音频驱动 | 自带 I2S 驱动 | `lua_module_audio` |
| 屏幕驱动 | 自带 SSD1306 驱动 | `lua_module_display` + LVGL |
| LED 控制 | 直接 GPIO | `lua_module_led_strip` |
| 引脚定义位置 | `main/boards/<name>/config.h` | `boards/<vendor>/<name>/board_*.yaml` |

**结论：引脚接口标准一样（都是 ESP-IDF 的 GPIO/I2S/SPI/I2C），只是配置文件格式不同。换 ESP-Claw 固件时，把小智的 GPIO 编号抄到 ESP-Claw 的 YAML 配置里就行。**

---

## ESP-Claw 已支持的、跟小智重叠的开发板

| 小智板子 | ESP-Claw 对应 | 引脚兼容性 |
|---------|--------------|-----------|
| esp-box-3 | `espressif/esp_box_3` | ✅ 完全兼容 |
| esp-sparkbot | `espressif/esp_sparkbot` | ✅ 完全兼容 |
| m5stack-core-s3 | `m5stack/m5stack_cores3` | ✅ 完全兼容 |
| bread-compact-wifi | ❌ 无对应 | 需自建 YAML 配置 |
| doit-s3-aibox | ❌ 无对应 | 需自建 YAML 配置 |

**对于 bread-compact-wifi 这类自搭板子，需要手动创建 ESP-Claw 板级配置文件。**
