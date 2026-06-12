// board.h — 最小 stub，满足小智音频代码的 include 依赖
// 小智的 audio_codec.cc 引用了 board.h 中的 Board::GetInstance()
// 我们用自己的 hal/board.h 提供 Board 类，这里只做桥接
#pragma once

#include "hal/board.h"

// 小智代码里用到的 Display 前向声明
class Display;
