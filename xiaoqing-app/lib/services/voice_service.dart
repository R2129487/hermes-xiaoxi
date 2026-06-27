import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

/// 语音识别服务 — 基于 sherpa-onnx 流式 Paraformer
/// 边说边出字，体验接近微信
class VoiceService {
  OnlineRecognizer? _recognizer;
  OnlineStream? _stream;
  AudioRecorder? _recorder;
  bool _initialized = false;
  String? _lastError;
  bool _isRecording = false;
  StreamSubscription<List<int>>? _audioSubscription;

  // 流式识别回调
  Function(String text)? onPartialResult;
  Function(String text)? onFinalResult;

  // 定时器：周期性解码
  Timer? _decodeTimer;

  String? get lastError => _lastError;
  bool get isAvailable => _initialized;
  bool get isRecording => _isRecording;

  /// 初始化语音识别引擎
  Future<bool> init() async {
    if (_initialized) return true;
    _lastError = null;

    try {
      // 解压流式模型到缓存目录
      final dir = await getTemporaryDirectory();
      final modelDir = Directory('${dir.path}/streaming_paraformer_zh');
      if (!await modelDir.exists()) {
        print('[VoiceService] 📦 首次加载，解压流式模型到 ${modelDir.path}');
        await modelDir.create(recursive: true);
        await _copyAsset('assets/models/streaming-paraformer-zh/encoder.onnx',
            '${modelDir.path}/encoder.onnx');
        await _copyAsset('assets/models/streaming-paraformer-zh/decoder.onnx',
            '${modelDir.path}/decoder.onnx');
        await _copyAsset('assets/models/streaming-paraformer-zh/tokens.txt',
            '${modelDir.path}/tokens.txt');
        print('[VoiceService] ✅ 流式模型解压完成');
      }

      // 检查模型文件
      final encoderFile = File('${modelDir.path}/encoder.onnx');
      final decoderFile = File('${modelDir.path}/decoder.onnx');
      final tokensFile = File('${modelDir.path}/tokens.txt');
      if (!await encoderFile.exists() ||
          !await decoderFile.exists() ||
          !await tokensFile.exists()) {
        _lastError = '流式模型文件缺失，尝试重新解压';
        print('[VoiceService] ❌ $_lastError');
        await modelDir.delete(recursive: true);
        return false;
      }

      print('[VoiceService] ⚙️ 创建流式识别引擎...');
      final config = OnlineRecognizerConfig(
        model: OnlineModelConfig(
          paraformer: OnlineParaformerModelConfig(
            encoder: encoderFile.path,
            decoder: decoderFile.path,
          ),
          tokens: tokensFile.path,
          numThreads: 4,
          provider: 'cpu',
          debug: false,
        ),
        decodingMethod: 'greedy_search',
        enableEndpoint: true,
        rule1MinTrailingSilence: 2.4,  // 2.4秒静音 → 第一句结束
        rule2MinTrailingSilence: 1.2,  // 1.2秒静音 → 后续句结束
        rule3MinUtteranceLength: 20,   // 最长20秒
      );

      _recognizer = OnlineRecognizer(config);
      _recorder = AudioRecorder();
      _initialized = true;
      _lastError = null;
      print('[VoiceService] ✅ 流式语音引擎初始化成功');
      return true;
    } catch (e) {
      _lastError = '$e';
      print('[VoiceService] ❌ 初始化失败: $e');
      return false;
    }
  }

  /// 开始录音并实时识别
  Future<bool> startRecording() async {
    if (!_initialized || _recognizer == null || _recorder == null) {
      print('[VoiceService] 引擎未初始化');
      return false;
    }

    // 检查权限
    if (!await _recorder!.hasPermission()) {
      final granted = await Permission.microphone.request();
      if (!granted.isGranted) {
        _lastError = '没有麦克风权限';
        print('[VoiceService] ❌ $_lastError');
        return false;
      }
    }

    try {
      // 创建新的识别流
      _stream = _recognizer!.createStream();
      _isRecording = true;

      // 配置录音参数：16kHz, 单声道, 16bit
      const config = RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
      );

      // 开始录音，获取音频流
      final stream = await _recorder!.startStream(config);

      // 监听音频数据，实时喂给识别器
      _audioSubscription = stream.listen((audioData) {
        if (!_isRecording || _stream == null) return;

        // PCM 16bit → float32
        final bytes = Uint8List.fromList(audioData);
        final samples = Float32List(bytes.length ~/ 2);
        for (int i = 0; i < samples.length; i++) {
          samples[i] =
              ByteData.view(bytes.buffer, i * 2, 2).getInt16(0, Endian.little) /
                  32768.0;
        }

        // 喂给识别器
        _stream!.acceptWaveform(samples: samples, sampleRate: 16000);

        // 如果识别器准备好了解码
        while (_recognizer!.isReady(_stream!)) {
          _recognizer!.decode(_stream!);
        }

        // 获取部分结果
        final result = _recognizer!.getResult(_stream!);
        final text = result.text.trim();
        if (text.isNotEmpty) {
          onPartialResult?.call(text);
        }

        // 检测端点（说话结束）
        if (_recognizer!.isEndpoint(_stream!)) {
          // 获取这一句的最终结果
          final finalResult = _recognizer!.getResult(_stream!);
          final finalText = finalResult.text.trim();
          if (finalText.isNotEmpty) {
            onFinalResult?.call(finalText);
          }
          // 重置流，准备下一句
          _recognizer!.reset(_stream!);
        }
      });

      print('[VoiceService] 🎤 开始流式录音');
      return true;
    } catch (e) {
      _lastError = '$e';
      _isRecording = false;
      print('[VoiceService] ❌ 开始录音失败: $e');
      return false;
    }
  }

  /// 停止录音，返回最终识别结果
  Future<String?> stopRecording() async {
    if (!_isRecording || _recorder == null) return null;

    try {
      _isRecording = false;

      // 停止录音
      final path = await _recorder!.stop();
      await _audioSubscription?.cancel();
      _audioSubscription = null;

      if (_stream == null || _recognizer == null) return null;

      // 刷新剩余数据
      while (_recognizer!.isReady(_stream!)) {
        _recognizer!.decode(_stream!);
      }

      // 获取最终结果
      final result = _recognizer!.getResult(_stream!);
      final text = result.text.trim();

      // 释放流
      _stream!.free();
      _stream = null;

      print('[VoiceService] 📝 最终识别结果: $text');
      return text.isEmpty ? null : text;
    } catch (e) {
      _lastError = '$e';
      print('[VoiceService] ❌ 停止录音失败: $e');
      return null;
    }
  }

  Future<void> _copyAsset(String assetPath, String destPath) async {
    final data = await rootBundle.load(assetPath);
    final file = File(destPath);
    await file.writeAsBytes(data.buffer.asUint8List());
  }

  void dispose() {
    _isRecording = false;
    _audioSubscription?.cancel();
    _decodeTimer?.cancel();
    _stream?.free();
    _stream = null;
    _recognizer?.free();
    _recognizer = null;
    _recorder?.dispose();
    _recorder = null;
    _initialized = false;
  }
}
