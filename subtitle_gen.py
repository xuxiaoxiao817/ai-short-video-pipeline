"""
字幕生成模块 - 使用 faster-whisper 对配音做语音识别，生成 SRT 字幕

流程：
1. 对完整音频做 ASR，得到逐句/逐词时间戳
2. 将时间戳映射到分镜
3. 输出 SRT 字幕文件 + JSON 时间线
"""

from pathlib import Path
from typing import Optional

from config import (
    AUDIO_DIR, SUBTITLE_DIR, SCRIPT_DIR,
)
from utils import save_json, format_timestamp, slugify, to_simplified


# 导入 faster-whisper（可选依赖）
_whisper_available = False
try:
    from faster_whisper import WhisperModel
    _whisper_available = True
except ImportError:
    pass


def transcribe_audio(
    audio_path: Path,
    model_size: str = "base",
    device: str = "cpu",
    language: str = "zh",
) -> list[dict]:
    """
    使用 faster-whisper 转录音频

    Args:
        audio_path: 音频文件路径
        model_size: Whisper 模型大小 (tiny/base/small/medium/large-v3)
        device: 运行设备 (cpu/cuda)
        language: 语言代码 (zh/en/...)

    Returns:
        识别结果列表: [{start, end, text}]
    """
    if not _whisper_available:
        print("[WARN]  faster-whisper 未安装，请执行: pip install faster-whisper")
        print("   将使用字幕时间预估模式...")
        return _estimate_timeline(audio_path)

    print("[MIC] 正在运行 Whisper ASR...")
    print(f"   模型: {model_size}, 设备: {device}")

    model = WhisperModel(model_size, device=device, compute_type="int8")
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=5,
        word_timestamps=True,
    )

    results = []
    for seg in segments:
        text = to_simplified(seg.text.strip())
        results.append({
            "start": seg.start,
            "end": seg.end,
            "text": text,
        })
        print(f"   [{seg.start:.1f}s - {seg.end:.1f}s] {text}")

    print(f"[OK] 转录完成，共 {len(results)} 句")
    return results


def _estimate_timeline(audio_path: Path) -> list[dict]:
    """
    当 Whisper 不可用时，根据音频时长和文本估算时间线
    用于开发调试阶段
    """
    import math

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return []

    # 尝试获取音频时长
    duration = 10.0  # 默认 10 秒

    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(audio_path))
        duration = len(audio) / 1000.0  # 毫秒转秒
    except Exception:
        # 尝试用 ffprobe
        import subprocess
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of",
                 "default=noprint_wrappers=1:nokey=1",
                 str(audio_path)],
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip():
                duration = float(result.stdout.strip())
        except Exception:
            pass

    # 查找对应的时间线文件
    timeline_path = AUDIO_DIR / f"{audio_path.stem.replace('_full', '')}_timeline.json"
    timeline_path2 = AUDIO_DIR / f"{audio_path.stem}_timeline.json"

    timeline_data = None
    import json
    for tp in [timeline_path, timeline_path2]:
        if tp.exists():
            timeline_data = json.loads(Path(tp).read_text(encoding="utf-8"))
            break

    if timeline_data and "scenes" in timeline_data:
        scenes = timeline_data["scenes"]
        if scenes and duration > 0:
            # 按文本长度比例分配时长
            total_chars = sum(len(s["text"]) for s in scenes)
            results = []
            current_time = 0.0
            for s in scenes:
                ratio = len(s["text"]) / total_chars if total_chars > 0 else 1.0 / len(scenes)
                seg_duration = duration * ratio
                results.append({
                    "start": current_time,
                    "end": current_time + seg_duration,
                    "text": s["text"],
                })
                current_time += seg_duration
            return results

    # 最后兜底
    return [
        {"start": 0.0, "end": duration, "text": "..."}
    ]


def generate_srt(segments: list[dict], output_path: Path) -> str:
    """
    将识别结果生成为 SRT 字幕文件

    Args:
        segments: [{start, end, text}, ...]
        output_path: 输出路径

    Returns:
        SRT 内容字符串
    """
    lines = []
    for i, seg in enumerate(segments, 1):
        start_ts = format_timestamp(seg["start"])
        end_ts = format_timestamp(seg["end"])
        text = to_simplified(seg["text"].strip())
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")

    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"[OK] 字幕已生成: {output_path} ({len(segments)} 条)")

    return content


def build_subtitle_timeline(
    segments: list[dict],
    script: dict,
) -> list[dict]:
    """
    将 ASR 结果映射到分镜，构造视频合成所需的时间线

    Args:
        segments: ASR 识别结果 [{start, end, text}]
        script: 脚本 dict

    Returns:
        时间线列表: [{index, narration, start, end, image_path}]
    """
    # 简单映射：将 ASR 句子依次匹配到分镜
    timeline = []
    asr_idx = 0
    for scene_idx, scene in enumerate(script["scenes"]):
        scene_text = scene["narration"]
        # 找到属于这个分镜的 ASR 句子
        scene_segments = []
        while asr_idx < len(segments):
            seg = segments[asr_idx]
            scene_segments.append(seg)
            asr_idx += 1
            # 如果这句话的长度占分镜文本的 50% 以上，认为已覆盖
            cumul_text = "".join(s["text"] for s in scene_segments)
            # 累计文本匹配到原文本中
            if len(cumul_text) >= len(scene_text) * 0.5:
                break

        if scene_segments:
            start = scene_segments[0]["start"]
            end = scene_segments[-1]["end"]
        else:
            start = 0.0
            end = 0.0

        timeline.append({
            "index": scene_idx,
            "narration": scene_text,
            "start": start,
            "end": end,
            "duration": end - start,
        })

    return timeline


def generate_subtitles(
    audio_path: Path,
    script: dict,
    topic: str,
    whisper_model: str = "base",
) -> tuple[Path, list[dict]]:
    """
    完整流程：音频转写 -> 映射分镜 -> 生成 SRT

    Args:
        audio_path: 音频文件路径
        script: 脚本 dict
        topic: 主题
        whisper_model: Whisper 模型大小

    Returns:
        (srt_path, timeline)
    """
    safe_name = slugify(topic)

    # 1. 转写
    segments = transcribe_audio(audio_path, model_size=whisper_model)

    # 2. 映射到分镜
    timeline = build_subtitle_timeline(segments, script)

    # 3. 生成 SRT
    srt_path = SUBTITLE_DIR / f"{safe_name}.srt"
    generate_srt(segments, srt_path)

    # 4. 保存时间线 JSON
    timeline_path = SUBTITLE_DIR / f"{safe_name}_timeline.json"
    save_json({
        "timeline": timeline,
        "segments": segments,
        "srt_path": str(srt_path),
        "audio_path": str(audio_path),
    }, timeline_path)

    return srt_path, timeline


if __name__ == "__main__":
    # 测试
    test_segments = [
        {"start": 0.0, "end": 2.5, "text": "量子纠缠是量子力学中最神奇的现象之一。"},
        {"start": 2.5, "end": 5.0, "text": "它描述了两个粒子之间的一种神秘联系。"},
    ]
    srt = generate_srt(test_segments, Path("output/subtitles/test.srt"))
    print(srt)
