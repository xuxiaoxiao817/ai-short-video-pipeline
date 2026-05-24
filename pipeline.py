"""
Pipeline 主流程 - 一键串联全流程

用法:
    python pipeline.py --topic "量子纠缠是什么？"

流程:
    1. 脚本生成 (DeepSeek)
    2. 配音合成 (MiniMax TTS)
    3. 配图生成 (MiniMax 文生图)
    4. 字幕生成 (Whisper)
    5. 视频合成 (moviepy)
"""

import argparse
import json
import sys
import time
from pathlib import Path

from config import (
    ensure_dirs, validate_config,
    SCRIPT_DIR, AUDIO_DIR, IMAGE_DIR, SUBTITLE_DIR, VIDEO_DIR,
)
from utils import slugify, load_json


def run_pipeline(topic: str, custom_prompt: str = "", bgm_path: str = ""):
    """
    运行完整视频生成流水线

    Args:
        topic: 视频主题
        custom_prompt: 可选的自定义脚本要求
        bgm_path: 可选的 BGM 音乐文件路径
    """
    start_time = time.time()
    print("=" * 60)
    print(f"[VIDEO] AI 短视频流水线启动")
    print(f"   主题: {topic}")
    print("=" * 60)
    print()

    # -----------------------------------------------------------
    # 0. 准备工作
    # -----------------------------------------------------------
    ensure_dirs()
    if not validate_config():
        print("[FAIL] 配置验证失败，请检查 .env 文件")
        sys.exit(1)

    safe_name = slugify(topic)

    # -----------------------------------------------------------
    # 1. 脚本生成
    # -----------------------------------------------------------
    print("\n" + "-" * 40)
    print("[NOTE] 阶段 1/5: 脚本生成")
    print("-" * 40)

    # 检查是否已有缓存脚本
    script_path = SCRIPT_DIR / f"{safe_name}.json"
    if script_path.exists():
        print(f"[FILE] 使用缓存脚本: {script_path}")
        script = load_json(script_path)
    else:
        from script_gen import generate_script
        script = generate_script(topic, custom_prompt or None)

    print(f"   视频标题: {script.get('title', '')}")
    print(f"   分镜数: {len(script.get('scenes', []))}")
    print()

    # -----------------------------------------------------------
    # 2. 配音生成
    # -----------------------------------------------------------
    print("-" * 40)
    print("[AUDIO] 阶段 2/5: 配音生成")
    print("-" * 40)

    audio_path = AUDIO_DIR / f"{safe_name}_full.mp3"
    if audio_path.exists():
        print(f"[FILE] 使用缓存音频: {audio_path}")
    else:
        from tts_gen import generate_full_audio
        generate_full_audio(script, topic)

    print()

    # -----------------------------------------------------------
    # 3. 配图生成
    # -----------------------------------------------------------
    print("-" * 40)
    print("[IMAGE] 阶段 3/5: 配图生成")
    print("-" * 40)

    # 检查已有图片
    existing_images = sorted(IMAGE_DIR.glob(f"{safe_name}_scene_*.png"))
    expected_count = len(script["scenes"])

    if len(existing_images) >= expected_count:
        print(f"[FILE] 使用缓存图片: {len(existing_images)} 张")
    else:
        from image_gen import generate_scene_images
        generate_scene_images(script, topic)

    print()

    # -----------------------------------------------------------
    # 4. 字幕生成
    # -----------------------------------------------------------
    print("-" * 40)
    print("[NOTE] 阶段 4/5: 字幕生成")
    print("-" * 40)

    srt_path = SUBTITLE_DIR / f"{safe_name}.srt"
    if srt_path.exists():
        print(f"[FILE] 使用缓存字幕: {srt_path}")
    else:
        from subtitle_gen import generate_subtitles
        try:
            audio_full = AUDIO_DIR / f"{safe_name}_full.mp3"
            if audio_full.exists():
                generate_subtitles(audio_full, script, topic)
            else:
                print("[WARN]  未找到音频文件，将使用时间预估模式")
        except Exception as e:
            print(f"[WARN]  字幕生成异常: {e}")
            print("   将使用时间预估模式继续...")

    print()

    # -----------------------------------------------------------
    # 5. 视频合成
    # -----------------------------------------------------------
    print("-" * 40)
    print("[VIDEO] 阶段 5/5: 视频合成")
    print("-" * 40)

    from video_comp import compose_from_pipeline_data

    # BGM 处理
    bgm_path_obj = None
    if bgm_path:
        bgm_path_obj = Path(bgm_path)
        if not bgm_path_obj.exists():
            print(f"[WARN]  BGM 文件不存在: {bgm_path}")
            bgm_path_obj = None

    # 如果没有指定 BGM，尝试使用 MiniMax 生成
    if bgm_path_obj is None and "bgm_style" in script:
        print("   将尝试使用背景音乐...")
        bgm_style = script.get("bgm_style", "轻快")
        generated_bgm = _generate_bgm(bgm_style, topic)
        if generated_bgm:
            bgm_path_obj = generated_bgm

    # 合成
    actual_video_path = None
    try:
        video_path = compose_from_pipeline_data(
            script=script,
            image_dir=IMAGE_DIR,
            audio_path=AUDIO_DIR / f"{safe_name}_full.mp3",
            subtitle_dir=SUBTITLE_DIR,
            topic=topic,
            bgm_path=bgm_path_obj,
        )
        print(f"\n[OK] 视频生成成功！")
        print(f"   [FILE] {video_path}")
        actual_video_path = video_path
    except Exception as e:
        print(f"\n[FAIL] 视频合成失败: {e}")
        import traceback
        traceback.print_exc()

    # -----------------------------------------------------------
    # 完成
    # -----------------------------------------------------------
    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"[FLAG] 流水线完成，耗时 {elapsed:.1f} 秒")
    if actual_video_path:
        print(f"   输出: {actual_video_path}")
    print(f"{'=' * 60}")


def _generate_bgm(style: str, topic: str) -> Path:
    """
    使用 MiniMax 音乐生成 API 生成背景音乐
    如果 API 调用失败，返回 None
    """
    from config import MINIMAX_MUSIC_ENDPOINT, MINIMAX_MUSIC_MODEL, BGM_DIR
    from utils import make_minimax_headers, retry_on_failure
    from utils import slugify
    import requests

    safe_name = slugify(topic)
    output_path = BGM_DIR / f"{safe_name}_bgm.mp3"

    if output_path.exists():
        print(f"[FILE] 使用缓存 BGM: {output_path}")
        return output_path

    print(f"[MUSIC] 正在使用 MiniMax 生成背景音乐...")
    print(f"   风格: {style}")

    headers = make_minimax_headers()

    payload = {
        "model": MINIMAX_MUSIC_MODEL,
        "style": style,
        "duration": 30,  # 短音乐片段
        "instrumental": True,  # 纯音乐
    }

    def _do_request():
        resp = requests.post(
            MINIMAX_MUSIC_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        result = retry_on_failure(_do_request)
        # 解析音乐 URL
        music_url = None
        if isinstance(result, dict):
            data = result.get("data") or result.get("music")
            if isinstance(data, dict) and not data:
                data = None
            if isinstance(data, list) and len(data) > 0:
                music_url = data[0].get("url") or data[0].get("music_url")

        if music_url:
            from utils import download_file
            download_file(music_url, output_path)
            print(f"[OK] BGM 已生成: {output_path}")
            return output_path
        else:
            print(f"[WARN]  无法解析音乐生成结果")
            return None

    except Exception as e:
        print(f"[WARN]  BGM 生成失败: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="AI 短视频自动生成流水线"
    )
    parser.add_argument(
        "--topic", "-t",
        type=str,
        required=True,
        help="视频主题",
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default="",
        help="脚本生成的额外要求",
    )
    parser.add_argument(
        "--bgm", "-b",
        type=str,
        default="",
        help="BGM 音乐文件路径（留空则尝试自动生成）",
    )
    parser.add_argument(
        "--skip-script",
        action="store_true",
        help="跳过脚本生成（复用已有的缓存）",
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="跳过配音生成",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="跳过配图生成",
    )
    parser.add_argument(
        "--skip-subtitles",
        action="store_true",
        help="跳过字幕生成",
    )

    args = parser.parse_args()

    run_pipeline(
        topic=args.topic,
        custom_prompt=args.prompt,
        bgm_path=args.bgm,
    )


if __name__ == "__main__":
    main()
