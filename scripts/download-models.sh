#!/bin/bash
# 下载语音识别模型（~160MB，不进git）
# 用法: bash scripts/download-models.sh

set -e

MODELS_DIR="xiaoqing-app/assets/models"
ZIPFORMER_DIR="$MODELS_DIR/streaming-zipformer-zh-int8"
HF_BASE="https://hf-mirror.com/csukuangfj/sherpa-onnx-streaming-zipformer-zh-int8-2025-06-30/resolve/main"

echo "📦 下载 Zipformer 流式语音识别模型..."
mkdir -p "$ZIPFORMER_DIR"

for f in encoder.int8.onnx decoder.onnx joiner.int8.onnx tokens.txt; do
    if [ -f "$ZIPFORMER_DIR/$f" ]; then
        echo "  ✓ $f 已存在，跳过"
    else
        echo "  ↓ 下载 $f ..."
        curl -sL "$HF_BASE/$f" -o "$ZIPFORMER_DIR/$f"
        echo "  ✓ $f ($(du -h "$ZIPFORMER_DIR/$f" | cut -f1))"
    fi
done

echo ""
echo "✅ 模型下载完成！总计 $(du -sh "$ZIPFORMER_DIR" | cut -f1)"
echo "   路径: $ZIPFORMER_DIR"
