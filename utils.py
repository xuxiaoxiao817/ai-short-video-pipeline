"""工具函数"""

import json
import re
import time
from pathlib import Path
from typing import Optional

import requests


def save_json(data: dict, filepath: Path) -> None:
    """保存 JSON 文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath: Path) -> Optional[dict]:
    """加载 JSON 文件"""
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def download_file(url: str, save_path: Path) -> Path:
    """下载文件到本地"""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=(30, 300))
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)
    return save_path


def make_minimax_headers() -> dict:
    """构造 MiniMax API 请求头"""
    from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    if MINIMAX_GROUP_ID:
        headers["MiniMax-Header-Group-Id"] = MINIMAX_GROUP_ID
    return headers


def retry_on_failure(func, max_retries=3, delay=2.0):
    """简单重试装饰器"""
    if max_retries <= 0:
        return func()
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt == max_retries - 1:
                raise
            print(f"  重试 {attempt + 1}/{max_retries}: {e}")
            time.sleep(delay * (attempt + 1))


def format_timestamp(seconds: float) -> str:
    """将秒数转为 SRT 时间戳格式: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def slugify(text: str, max_len: int = 50) -> str:
    """
    将文本转为路径安全的文件名 slug

    保留中文、字母、数字，其余非安全字符替换为连字符，
    连字符合并、去首尾，截断到 max_len。
    """
    # 替换非法文件名字符和标点为连字符
    safe = re.sub(r'[\\\\/*?:\"<>|\s,，。！？、；：""\'\'（）()【】\[\]《》<>「」『』]+', '-', text)
    # 合并连续连字符
    safe = re.sub(r'-+', '-', safe)
    # 去首尾连字符
    safe = safe.strip('-')
    # 截断
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip('-')
    return safe or "video"
