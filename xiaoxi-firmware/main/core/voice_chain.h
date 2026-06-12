#pragma once

// 听觉链路：按钮/唤醒词 → 录音 → ASR → Chat → TTS → 播放
void run_voice_interaction();

// 启动语音任务（后台持续监听唤醒词）
void start_voice_task();

// 停止语音任务
void stop_voice_task();
