"""配置管理 - 从 .env 文件加载 API Keys 和各项配置"""

import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# 强制加载 .env（确保在 code_execution 沙箱外也能工作）
_env_path = find_dotenv()
if _env_path:
    load_dotenv(_env_path)
else:
    load_dotenv()

# ============================================================
# 项目路径
# ============================================================
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# 各模块输出子目录
SCRIPT_DIR = OUTPUT_DIR / "scripts"
AUDIO_DIR = OUTPUT_DIR / "audio"
IMAGE_DIR = OUTPUT_DIR / "images"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"
VIDEO_DIR = OUTPUT_DIR / "videos"
BGM_DIR = OUTPUT_DIR / "bgm"

# ============================================================
# DeepSeek API
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ============================================================
# MiniMax API (Token Plan)
# ============================================================
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")
MINIMAX_BASE_URL = "https://api.minimaxi.com"

# --- TTS ---
MINIMAX_TTS_ENDPOINT = f"{MINIMAX_BASE_URL}/v1/t2a_pro"
MINIMAX_TTS_MODEL = "speech-02"
MINIMAX_TTS_VOICE_ID = "female-shaonv"  # 标准女声

# --- Image Generation ---
MINIMAX_IMAGE_ENDPOINT = f"{MINIMAX_BASE_URL}/v1/image_generation"
MINIMAX_IMAGE_MODEL = "image-01"

# --- Music Generation ---
MINIMAX_MUSIC_ENDPOINT = f"{MINIMAX_BASE_URL}/v1/music_generation"
MINIMAX_MUSIC_MODEL = "music-01"

# ============================================================
# 视频参数（竖屏 9:16）
# ============================================================
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Ken Burns 缩放
KEN_BURNS_ZOOM_START = 1.0
KEN_BURNS_ZOOM_END = 1.08

# 字幕样式
SUBTITLE_FONT_SIZE = 48
SUBTITLE_FONT_COLOR = "white"
SUBTITLE_BG_COLOR = "rgba(0, 0, 0, 0.5)"
SUBTITLE_POSITION = ("center", "bottom")

# 视频输出文件名
VIDEO_FILENAME = "output_video.mp4"


def ensure_dirs():
    """创建所有输出目录"""
    for d in [OUTPUT_DIR, SCRIPT_DIR, AUDIO_DIR, IMAGE_DIR,
              SUBTITLE_DIR, VIDEO_DIR, BGM_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def validate_config():
    """检查关键配置是否缺失，返回 True/False"""
    missing = []
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY")
    if not MINIMAX_API_KEY:
        missing.append("MINIMAX_API_KEY")
    if not MINIMAX_GROUP_ID:
        missing.append("MINIMAX_GROUP_ID")

    if missing:
        print(f"[WARN]  以下环境变量未设置: {', '.join(missing)}")
        print(f"   请复制 .env.example 为 .env 并填入你的 API Key")
        return False

    print("[OK] 配置检查通过")
    print(f"  DeepSeek: {DEEPSEEK_API_KEY[:8]}...{DEEPSEEK_API_KEY[-4:]}")
    print(f"  MiniMax:  {MINIMAX_API_KEY[:10]}...{MINIMAX_API_KEY[-4:]}")
    print(f"  GroupID:  {MINIMAX_GROUP_ID[:8]}...{MINIMAX_GROUP_ID[-4:]}")
    return True
