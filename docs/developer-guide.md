# 开发者指南

## AI 短视频自动生成系统

**文档版本**：v1.0  
**创建日期**：2026-05-24

---

## 1. 开发环境搭建

### 1.1 前置要求

```bash
# Python 3.10+
python --version

# 推荐：使用虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 安装开发依赖
pip install -r requirements.txt
pip install pytest mypy black
```

### 1.2 环境配置

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

---

## 2. 模块开发指南

### 2.1 代码规范

- **约定优于配置**：模块名、函数名、变量名使用 snake_case
- **类型注解**：所有公开函数必须包含类型注解
- **文档字符串**：模块级别有 docstring，函数有 Args/Returns 说明
- **错误处理**：API 调用使用 `retry_on_failure`，其他异常使用 try/except

### 2.2 模块间契约

每个阶段模块遵循以下模式：

```
def generate_xxx(input_data, topic) -> output_path_or_data:
    # 1. 检查缓存
    # 2. 调用 API 或本地处理
    # 3. 保存到 output/{type}/
    # 4. 返回结果
```

**模块输入/输出约定**：

| 模块 | 输入 | 输出 | 缓存路径 |
|------|------|------|---------|
| script_gen | topic: str | script: dict | output/scripts/{slug}.json |
| tts_gen | script: dict, topic: str | audio_path: Path | output/audio/{slug}_full.mp3 |
| image_gen | script: dict, topic: str | scene_images: list[dict] | output/images/{slug}_scene_*.png |
| subtitle_gen | audio_path, script, topic | (srt_path, timeline) | output/subtitles/{slug}.srt |
| video_comp | script, images, audio, subtitles | video_path: Path | output/videos/{slug}.mp4 |

### 2.3 添加新的 TTS 引擎

在 `tts_gen.py` 中添加新的 TTS 引擎：

```python
def _synthesize_new_engine(
    text: str,
    output_path: Optional[Path] = None,
) -> Optional[bytes]:
    """新的 TTS 引擎实现"""
    # 实现逻辑...
    pass
```

然后在 `synthesize_speech()` 的尝试链中加入：

```python
def synthesize_speech(...):
    # 已有：MiniMax → Edge TTS
    # 新增：
    if result is None:
        result = _synthesize_new_engine(text, output_path=output_path)
    return result
```

### 2.4 添加新的图片源

在 `image_gen.py` 中集成新的图片 API：

```python
def generate_image_via_new_api(
    prompt: str,
    aspect_ratio: str = "9:16",
) -> list[Path]:
    """新的图片生成 API"""
    pass

# 然后在 generate_image() 中添加尝试逻辑
```

### 2.5 自定义视频合成效果

编辑 `video_comp.py`：

- **Ken Burns 缩放范围**：修改 `KEN_BURNS_ZOOM_START` / `END` 或直接在 `_ken_burns_clip()` 中调整
- **转场效果**：在场景切换处添加 `fadein/fadeout` 持续时间
- **开场/片尾**：修改 `_render_title_frame()` 和 `_render_outro_frame()` 中的 PIL 渲染逻辑
- **字幕样式**：修改 `_render_subtitle_frame()` 中的字体、颜色、背景

---

## 3. API 参考

### 3.1 config 模块

```python
# 路径
PROJECT_ROOT           # 项目根目录 Path
OUTPUT_DIR             # 输出目录 Path
SCRIPT_DIR / AUDIO_DIR / IMAGE_DIR / SUBTITLE_DIR / VIDEO_DIR / BGM_DIR

# DeepSeek
DEEPSEEK_API_KEY       # API Key
DEEPSEEK_BASE_URL      # API 基础 URL
DEEPSEEK_MODEL         # 模型名

# MiniMax
MINIMAX_API_KEY        # API Key
MINIMAX_GROUP_ID       # 分组 ID
MINIMAX_TTS_ENDPOINT   # TTS 端点 URL
MINIMAX_IMAGE_ENDPOINT # 文生图端点 URL

# 视频参数
VIDEO_WIDTH / VIDEO_HEIGHT  # 分辨率
VIDEO_FPS                   # 帧率
KEN_BURNS_ZOOM_START / END  # 缩放范围
SUBTITLE_FONT_SIZE          # 字幕字号

# 函数
ensure_dirs()          # 创建所有输出目录
validate_config()      # 检查 API Key 是否配置
```

### 3.2 utils 模块

```python
save_json(data: dict, filepath: Path) -> None
load_json(filepath: Path) -> Optional[dict]
download_file(url: str, save_path: Path) -> Path
make_minimax_headers() -> dict
retry_on_failure(func, max_retries=3, delay=2.0)
format_timestamp(seconds: float) -> str
slugify(text: str) -> str
```

### 3.3 script_gen 模块

```python
generate_script(
    topic: str,
    custom_prompt: Optional[str] = None,
) -> dict
```

### 3.4 tts_gen 模块

```python
synthesize_speech(
    text: str,
    output_path: Optional[Path] = None,
    voice_id: str = "female-shaonv",
    speed: float = 1.0,
) -> Optional[bytes]

generate_full_audio(script: dict, topic: str) -> Optional[Path]

generate_scene_audios(script: dict, topic: str) -> Optional[list[dict]]
```

### 3.5 image_gen 模块

```python
generate_image(
    prompt: str,
    model: str = "image-01",
    aspect_ratio: str = "9:16",
    n: int = 1,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
) -> list[Path]

generate_scene_images(
    script: dict,
    topic: str,
    aspect_ratio: str = "9:16",
) -> list[dict]
```

### 3.6 subtitle_gen 模块

```python
transcribe_audio(
    audio_path: Path,
    model_size: str = "base",
    device: str = "cpu",
    language: str = "zh",
) -> list[dict]

generate_srt(segments: list[dict], output_path: Path) -> str

generate_subtitles(
    audio_path: Path,
    script: dict,
    topic: str,
    whisper_model: str = "base",
) -> tuple[Path, list[dict]]
```

### 3.7 video_comp 模块

```python
compose_video(
    script: dict,
    image_paths: list[str],
    audio_path: str,
    srt_path: str,
    timeline: list[dict],
    topic: str,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.15,
    output_path: Optional[Path] = None,
) -> Path

compose_from_pipeline_data(
    script: dict,
    image_dir: Path,
    audio_path: Path,
    subtitle_dir: Path,
    topic: str,
    bgm_path: Optional[Path] = None,
) -> Path
```

### 3.8 pipeline 模块

```python
run_pipeline(
    topic: str,
    custom_prompt: str = "",
    bgm_path: str = "",
)
```

---

## 4. 测试

### 4.1 单元测试使用方式

每个模块可以独立运行测试：

```bash
# 测试脚本生成
python script_gen.py

# 测试 TTS 合成
python tts_gen.py

# 测试图片生成
python image_gen.py

# 测试字幕生成
python subtitle_gen.py

# 测试视频合成（需要 mock 数据）
python video_comp.py
```

### 4.2 端到端测试

```bash
# 完整流程
python pipeline.py --topic "测试主题"
```

### 4.3 验证视频输出

```bash
# 检查视频信息
ffprobe output/videos/xxx.mp4

# 常用命令行剪裁（FFmpeg）
ffmpeg -i output/videos/xxx.mp4 -ss 00:00:05 -t 00:00:10 -c copy trimmed.mp4
```

---

## 5. 扩展指南

### 5.1 支持横屏视频

修改 `config.py`：

```python
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080  # 16:9 横屏
```

同时修改 `image_gen.py` 中的 `aspect_ratio` 默认值：

```python
aspect_ratio: str = "16:9"
```

### 5.2 支持 OpenAI 替代 DeepSeek

编辑 `config.py`：

```python
DEEPSEEK_BASE_URL = "https://api.openai.com/v1"
DEEPSEEK_MODEL = "gpt-4o"
DEEPSEEK_API_KEY = os.getenv("OPENAI_API_KEY", "")
```

### 5.3 支持其他文生图引擎（Stable Diffusion）

在 `image_gen.py` 中添加：

```python
def generate_image_sd(
    prompt: str,
    sd_url: str = "http://localhost:7860/sdapi/v1/txt2img",
) -> list[Path]:
    """通过 Stable Diffusion WebUI API 生成图片"""
    # 实现逻辑
    pass
```

---

## 6. 常见开发问题

### 6.1 Windows 编码问题

Windows 终端默认使用 GBK 编码，可能导致 emoji 和中文输出乱码：

```python
# 在脚本开头设置环境变量
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```

本项目代码中已避免了 emoji 输出，确保兼容 GBK 终端。

### 6.2 moviepy 版本兼容

项目同时兼容 moviepy v1.x 和 v2.x：

```python
try:
    from moviepy import ImageClip  # v2.x
    MOVIEPY_V2 = True
except ImportError:
    from moviepy.editor import ImageClip  # v1.x
    MOVIEPY_V2 = False
```

### 6.3 MiniMax API 限流

MiniMax API 有速率限制。在 `image_gen.py` 中每个分镜间有 1 秒间隔。如果遇到限流错误，增大 `time.sleep()` 的等待时间。

---

## 7. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-05-24 | 初始版本，完成 5 阶段核心管道 |
