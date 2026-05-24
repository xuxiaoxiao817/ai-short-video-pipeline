"""
图片生成模块 - 调用 MiniMax 文生图 API 为脚本的每个分镜生成配图
"""

import json
import time
from pathlib import Path
from typing import Optional

import requests

from config import (
    MINIMAX_IMAGE_ENDPOINT, MINIMAX_IMAGE_MODEL,
    IMAGE_DIR,
)
from utils import download_file, make_minimax_headers, retry_on_failure, slugify


def generate_image(
    prompt: str,
    model: str = MINIMAX_IMAGE_MODEL,
    aspect_ratio: str = "9:16",
    n: int = 1,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
) -> list[Path]:
    """
    调用 MiniMax 文生图 API 生成图片

    Returns:
        生成的图片文件路径列表
    """
    headers = make_minimax_headers()

    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "n": n,
    }

    def _do_request():
        resp = requests.post(
            MINIMAX_IMAGE_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()

    print(f"[IMAGE] 正在调用 MiniMax 文生图...")
    print(f"   提示词: {prompt[:60]}...")

    result = retry_on_failure(_do_request)
    if result is None:
        return []

    # 解析返回结果
    # MiniMax 返回格式: {"id":"...","data":{"image_urls":["..."]},"base_resp":{"status_code":0,...}}
    image_urls = []
    data_field = result.get("data") if isinstance(result, dict) else {}

    if isinstance(data_field, dict):
        urls = data_field.get("image_urls") or data_field.get("urls") or []
        if isinstance(urls, list):
            image_urls.extend(urls)
    elif isinstance(data_field, list):
        for item in data_field:
            if isinstance(item, dict):
                url = item.get("url") or item.get("image_url") or ""
                if url:
                    image_urls.append(url)
            elif isinstance(item, str):
                image_urls.append(item)

    if not image_urls:
        print(f"[WARN] 图片 URL 解析失败: {json.dumps(result, ensure_ascii=False)[:200]}")
        return []

    # 下载图片
    output_dir = output_dir or IMAGE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for idx, url in enumerate(image_urls):
        if filename:
            img_name = f"{filename}_{idx}.png"
        else:
            img_name = f"img_{slugify(prompt)}_{idx}.png"
        save_path = output_dir / img_name
        try:
            download_file(url, save_path)
            saved_paths.append(save_path)
            print(f"[OK] 图片已保存: {save_path} ({len(saved_paths)}/{len(image_urls)})")
        except Exception as e:
            print(f"[FAIL] 下载失败: {url[:50]}... - {e}")

    return saved_paths


def generate_scene_images(
    script: dict,
    topic: str,
    aspect_ratio: str = "9:16",
) -> list[dict]:
    """
    根据脚本的分镜信息，为每个分镜生成配图
    """
    safe_name = slugify(topic)
    scene_images = []

    for i, scene in enumerate(script["scenes"]):
        prompt = scene.get("image_prompt", scene["narration"])
        paths = generate_image(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            n=1,
            filename=f"{safe_name}_scene_{i:02d}",
        )

        scene_images.append({
            "index": i,
            "prompt": prompt,
            "narration": scene["narration"],
            "image_paths": [str(p) for p in paths],
        })

        # 避免限流
        if i < len(script["scenes"]) - 1:
            time.sleep(1)

    return scene_images
