import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

/// 语音识别服务 — 基于 sherpa-onnx + Paraformer-tiny
/// 手机本地离线转写，不依赖网络和Google服务
class VoiceService {
  OfflineRecognizer? _recognizer;
  bool _initialized = false;
  String? _lastError;

  /// 最后的错误信息（供UI显示）
  String? get lastError => _lastError;

  /// 引擎是否就绪
  bool get isAvailable => _initialized;

  /// 初始化语音识别引擎
  Future<bool> init() async {
    if (_initialized) return true;
    _lastError = null;

    try {
      // 把assets里的模型文件解压到缓存目录
      final dir = await getTemporaryDirectory();
      final modelDir = Directory('${dir.path}/paraformer_zh_small');
      if (!await modelDir.exists()) {
        print('[VoiceService] 📦 首次加载，解压模型文件到 ${modelDir.path}');
        await modelDir.create(recursive: true);
        await _copyAsset('assets/models/paraformer-zh-small/model.int8.onnx',
            '${modelDir.path}/model.int8.onnx');
        await _copyAsset('assets/models/paraformer-zh-small/tokens.txt',
            '${modelDir.path}/tokens.txt');
        print('[VoiceService] ✅ 模型文件已解压完成');
      }

      // 检查模型文件是否存在
      final modelFile = File('${modelDir.path}/model.int8.onnx');
      final tokensFile = File('${modelDir.path}/tokens.txt');
      if (!await modelFile.exists() || !await tokensFile.exists()) {
        _lastError = '模型文件缺失，尝试重新解压';
        print('[VoiceService] ❌ $_lastError');
        await modelDir.delete(recursive: true);
        return false;
      }

      print('[VoiceService] ⚙️ 创建识别引擎配置...');
      final config = OfflineRecognizerConfig(
        model: OfflineModelConfig(
          paraformer: OfflineParaformerModelConfig(
            model: modelFile.path,
          ),
          tokens: tokensFile.path,
          numThreads: 4,
          provider: 'cpu',
          debug: false,
        ),
        decodingMethod: 'greedy_search',
      );

      _recognizer = OfflineRecognizer(config);
      _initialized = true;
      _lastError = null;
      print('[VoiceService] ✅ 语音引擎初始化成功');
      return true;
    } catch (e) {
      _lastError = '$e';
      print('[VoiceService] ❌ 初始化失败: $e');
      return false;
    }
  }

  /// WAV文件转文字
  Future<String?> transcribe(String wavPath) async {
    if (!_initialized || _recognizer == null) {
      print('[VoiceService] 引擎未初始化');
      return null;
    }

    try {
      // 读取WAV文件 → PCM float samples
      final file = File(wavPath);
      final bytes = await file.readAsBytes();

      // WAV头: 44字节, PCM 16bit mono
      final sampleRate = ByteData.view(bytes.buffer, 24, 4).getUint32(0, Endian.little);
      final dataSize = ByteData.view(bytes.buffer, 40, 4).getUint32(0, Endian.little);
      final samples = Float32List(dataSize ~/ 2);
      for (int i = 0; i < samples.length; i++) {
        samples[i] = ByteData.view(bytes.buffer, 44 + i * 2, 2).getInt16(0, Endian.little) / 32768.0;
      }

      // 创建stream
      final stream = _recognizer!.createStream();
      stream.acceptWaveform(samples: samples, sampleRate: sampleRate);

      // 解码
      _recognizer!.decode(stream);

      // 取结果
      final result = _recognizer!.getResult(stream);
      final text = result.text.trim();

      // 清理
      stream.free();

      print('[VoiceService] 📝 识别结果: $text');
      return text.isEmpty ? null : text;
    } catch (e) {
      print('[VoiceService] ❌ 识别失败: $e');
      return null;
    }
  }

  Future<void> _copyAsset(String assetPath, String destPath) async {
    final data = await rootBundle.load(assetPath);
    final file = File(destPath);
    await file.writeAsBytes(data.buffer.asUint8List());
  }

  void dispose() {
    _recognizer?.free();
    _recognizer = null;
    _initialized = false;
  }
}
