"""
配音生成模块 - 为脚本生成配音音频

有三种模式（按优先级）：
1. MiniMax TTS（高质量，需余额）
2. Edge TTS（免费，质量不错，无需 API Key）
3. 逐句合成（为每个分镜单独生成）
"""

import json
from pathlib import Path
from typing import Optional

import requests

from config import (
    MINIMAX_TTS_ENDPOINT, MINIMAX_TTS_MODEL, MINIMAX_TTS_VOICE_ID,
    AUDIO_DIR,
)
from utils import save_json, make_minimax_headers, retry_on_failure, slugify


# ============================================================
# 方式一：MiniMax TTS
# ============================================================

def _synthesize_minimax(
    text: str,
    voice_id: str = MINIMAX_TTS_VOICE_ID,
    model: str = MINIMAX_TTS_MODEL,
    speed: float = 1.0,
    output_path: Optional[Path] = None,
) -> Optional[bytes]:
    """
    调用 MiniMax TTS 合成语音

    Returns:
        成功返回音频二进制数据，失败（余额不足等）返回 None
    """
    headers = make_minimax_headers()

    payload = {
        "model": model,
        "text": text,
        "voice_id": voice_id,
        "speed": speed,
    }

    def _do_request():
        resp = requests.post(
            MINIMAX_TTS_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()

        # 检查返回类型
        content_type = resp.headers.get("content-type", "")
        if "json" in content_type:
            err = resp.json()
            code = err.get("base_resp", {}).get("status_code", 0)
            msg = err.get("base_resp", {}).get("status_msg", "")

            if code == 1008:
                print(f"[WARN]  MiniMax TTS 余额不足: {msg}")
                print(f"   将自动切换到 Edge TTS 免费方案")
                return None
            elif code != 0:
                print(f"[WARN]  MiniMax TTS 错误 [{code}]: {msg}")
                return None
            # 可能有 audio_file 字段
            audio_url = err.get("audio_file", "")
            if audio_url:
                audio_resp = requests.get(audio_url, timeout=60)
                return audio_resp.content
            return None

        return resp.content

    result = retry_on_failure(_do_request, max_retries=2)
    if result is None:
        return None

    if output_path and len(result) > 100:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(result)
        print(f"[AUDIO] MiniMax TTS 成功: {output_path} ({len(result) / 1024:.1f} KB)")
    elif output_path:
        print(f"[WARN]  音频数据过短 ({len(result)} bytes)，可能无效")

    return result


# ============================================================
# 方式二：Edge TTS 免费方案（备用）
# ============================================================

def _synthesize_edge(
    text: str,
    voice: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+0%",
    output_path: Optional[Path] = None,
) -> Optional[bytes]:
    """
    使用 Edge TTS（免费）合成中文语音

    Args:
        text: 文本
        voice: 发音人 (zh-CN-XiaoxiaoNeural 女声, zh-CN-YunxiNeural 男声)
        rate: 语速 (+0% 正常, -20% 慢, +20% 快)
        output_path: 保存路径
    """
    try:
        import edge_tts
    except ImportError:
        print("[WARN]  edge-tts 未安装，请执行: pip install edge-tts")
        return None

    print(f"[AUDIO] 使用 Edge TTS（免费）合成语音...")
    print(f"   文本: {text[:40]}... ({len(text)} 字)")

    async def _do_tts():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data

    import asyncio
    try:
        audio_data = asyncio.run(_do_tts())
    except Exception as e:
        print(f"[WARN]  Edge TTS 失败: {e}")
        return None

    if output_path and audio_data:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_data)
        print(f"[OK] Edge TTS 成功: {output_path} ({len(audio_data) / 1024:.1f} KB)")

    return audio_data


# ============================================================
# 统一合成接口
# ============================================================

def synthesize_speech(
    text: str,
    output_path: Optional[Path] = None,
    voice_id: str = MINIMAX_TTS_VOICE_ID,
    speed: float = 1.0,
) -> Optional[bytes]:
    """
    合成语音（自动选择：MiniMax -> Edge TTS 依次尝试）

    Args:
        text: 文本
        output_path: 保存路径
        voice_id: MiniMax 音色
        speed: 语速

    Returns:
        音频二进制数据，或 None
    """
    from config import MINIMAX_API_KEY

    # 先尝试 MiniMax
    if MINIMAX_API_KEY:
        print(f"\n[NET] 尝试 MiniMax TTS...")
        result = _synthesize_minimax(text, voice_id=voice_id, speed=speed,
                                     output_path=output_path)
        if result and len(result) > 1000:
            return result
    else:
        print(f"\n[NET] 未配置 MiniMax API Key，直接使用 Edge TTS")

    # 备用：Edge TTS
    print(f"\n[NET] 切换到 Edge TTS（免费）...")
    result = _synthesize_edge(text, output_path=output_path)
    if result:
        return result

    print("[FAIL] 所有 TTS 方案均失败")
    return None


# ============================================================
# 完整音频生成
# ============================================================

def generate_full_audio(script: dict, topic: str) -> Path:
    """
    将脚本全部分镜的旁白合成一个完整音频文件

    Args:
        script: 脚本 dict
        topic: 主题

    Returns:
        音频文件路径，失败时返回 None
    """
    all_texts = [scene["narration"] for scene in script["scenes"]]
    full_text = "".join(all_texts)

    safe_name = slugify(topic)
    output_path = AUDIO_DIR / f"{safe_name}_full.mp3"

    audio_data = synthesize_speech(
        text=full_text,
        output_path=output_path,
    )

    if audio_data is None:
        return None

    # 保存时间线
    timeline = [
        {"index": i, "text": scene["narration"]}
        for i, scene in enumerate(script["scenes"])
    ]
    timeline_path = AUDIO_DIR / f"{safe_name}_timeline.json"
    save_json({"scenes": timeline, "audio_file": str(output_path)}, timeline_path)

    return output_path


def generate_scene_audios(script: dict, topic: str) -> Optional[list[dict]]:
    """
    逐分镜合成语音

    Returns:
        每个分镜信息列表，或 None
    """
    safe_name = slugify(topic)
    scene_audios = []

    for i, scene in enumerate(script["scenes"]):
        text = scene["narration"]
        output_path = AUDIO_DIR / f"{safe_name}_scene_{i:02d}.mp3"

        data = synthesize_speech(text=text, output_path=output_path)
        if data is None:
            print(f"[WARN]  分镜 {i} 语音合成失败")
            continue

        scene_audios.append({
            "index": i,
            "text": text,
            "audio_path": str(output_path),
        })

    if not scene_audios:
        return None

    timeline_path = AUDIO_DIR / f"{safe_name}_timeline.json"
    save_json({"scenes": scene_audios}, timeline_path)
    return scene_audios


if __name__ == "__main__":
    # 测试
    test_script = {
        "title": "测试",
        "scenes": [
            {"narration": "量子纠缠是量子力学中最神奇的现象之一。"},
            {"narration": "它描述了两个粒子之间的一种神秘联系。"},
        ],
    }
    audio_path = generate_full_audio(test_script, "测试")
    if audio_path:
        print(f"音频已生成: {audio_path}")
    else:
        print("音频生成失败")
