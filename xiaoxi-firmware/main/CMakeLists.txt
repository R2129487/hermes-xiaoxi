# 小希固件 — C++ 模块化 CMakeLists

# === 搬自 xiaozhi-esp32 的音频驱动 ===
set(AUDIO_SOURCES
    # Codec 基类
    "audio/audio_codec.cc"
    # OGG 解码
    "audio/demuxer/ogg_demuxer.cc"
    # Codec 驱动
    "audio/codecs/no_audio_codec.cc"
    "audio/codecs/dummy_audio_codec.cc"
    "audio/codecs/es8311_audio_codec.cc"
    "audio/codecs/es8374_audio_codec.cc"
    "audio/codecs/es8388_audio_codec.cc"
    "audio/codecs/es8389_audio_codec.cc"
    "audio/codecs/box_audio_codec.cc"
    # 音频处理器
    "audio/processors/audio_debugger.cc"
)

# 音频处理器（根据 Kconfig 选择）
if(CONFIG_USE_AUDIO_PROCESSOR)
    list(APPEND AUDIO_SOURCES "audio/processors/afe_audio_processor.cc")
else()
    list(APPEND AUDIO_SOURCES "audio/processors/no_audio_processor.cc")
endif()

# 唤醒词（ESP-SR WakeNet，所有芯片都编译）
list(APPEND AUDIO_SOURCES "audio/wake_words/esp_wake_word.cc")

# === 我们自己写的模块 ===
set(XIAOXI_SOURCES
    "main.cc"
    # Core
    "core/event_bus.cc"
    "core/state_machine.cc"
    "core/config.cc"
    "core/session.cc"
    "core/application.cc"
    "core/voice_chain.cc"
    # Audio 接口
    "audio/audio_pipeline.cc"
    # Vision
    "vision/camera.cc"
    # Motion
    "motion/actuator.cc"
    # Output
    "output/output.cc"
    # Comm
    "comm/comm.cc"
    "comm/wifi_manager.cc"
    # HAL
    "hal/board.cc"
    # Sensors
    "sensors/radar.cc"
)

set(ALL_SOURCES ${AUDIO_SOURCES} ${XIAOXI_SOURCES})

set(INCLUDE_DIRS
    "."
    "stubs"
    "core"
    "audio"
    "audio/codecs"
    "audio/demuxer"
    "audio/processors"
    "audio/wake_words"
    "vision"
    "motion"
    "output"
    "comm"
    "sensors"
    "hal"
)

idf_component_register(
    SRCS ${ALL_SOURCES}
    INCLUDE_DIRS ${INCLUDE_DIRS}
    WHOLE_ARCHIVE
    PRIV_REQUIRES
        nvs_flash
        esp_wifi
        esp_event
        esp_netif
        esp_http_client
        esp_http_server
        esp_timer
        esp_driver_gpio
        esp_driver_i2c
        esp_driver_i2s
        esp_driver_spi
        esp_app_format
        app_update
        spi_flash
        console
        efuse
        json
        bt
        esp-sr
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE XIAOXI_FIRMWARE=1)
