# AI 短视频自动生成系统

> 基于 DeepSeek + MiniMax API 的知识科普类短视频全自动生产线

输入一个主题，自动完成 **脚本写作 → 语音配音 → 配图生成 → 字幕制作 → 视频合成** 全流程，输出可直接发布的竖屏短视频。

---

## 快速体验

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（复制模板并填入密钥）
cp .env.example .env
# 编辑 .env 文件填入 DeepSeek 和 MiniMax 的 API Key

# 3. 一键生成视频
python pipeline.py --topic "什么是量子纠缠？"
```

---

## 功能特性

- **全自动流程**：输入主题即可输出 MP4 视频，无需人工干预
- **结构化脚本**：DeepSeek 生成包含旁白、画面描述、BGM 风格的 JSON 脚本
- **高品质配音**：优先调用 MiniMax Speech-02 TTS，余额不足时自动回退到 Edge TTS（免费）
- **AI 配图**：调用 MiniMax 文生图 API，按分镜生成 9:16 竖屏插图
- **字幕对齐**：faster-whisper 精确时间戳 → SRT 字幕；无 GPU 时自动切换到时间预估模式
- **Ken Burns 动效**：图片缓慢缩放，避免静态画面枯燥
- **开场/片尾**：自动添加标题画面和引导关注片尾
- **背景音乐**：支持本地 BGM 文件混音

---

## 系统要求

- Python 3.10+
- FFmpeg（moviepy 自动附带，无需单独安装）
- 网络连接（API 调用 + Whisper 模型下载）

### Windows 终端编码

Windows 终端默认 GBK 编码可能导致中文乱码。执行以下任一操作：
```bash
# 方法 1：运行前切换到 UTF-8
chcp 65001

# 方法 2：在 PowerShell 配置文件中设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```
或使用 Windows Terminal 等支持 UTF-8 的终端。

### API 密钥

| 服务 | 用途 | 获取方式 |
|------|------|---------|
| DeepSeek | 脚本生成（LLM） | [platform.deepseek.com](https://platform.deepseek.com) |
| MiniMax | 文生图、TTS（可选） | [platform.minimaxi.com](https://platform.minimaxi.com) |

> MiniMax TTS 为可选项：有余额时自动使用，余额不足时无缝切换到 Edge TTS（免费）。

---

## 使用方法

### 基本用法

```bash
# 生成一个完整视频
python pipeline.py --topic "光速为什么是宇宙速度极限？"

# 带额外脚本要求
python pipeline.py --topic "黑洞" --prompt "用霍金的故事引入，30秒以内"

# 使用本地背景音乐
python pipeline.py --topic "相对论" --bgm "music/background.mp3"
```

### 跳过已完成的阶段

每个阶段的输出会缓存到 `output/` 目录，第二次运行相同主题时会自动跳过已完成的步骤：

```bash
# 只重新生成视频（不重新调 API）
python pipeline.py --topic "量子纠缠" --skip-script --skip-tts --skip-images --skip-subtitles
```

### 输出目录结构

```
output/
├── scripts/          # 脚本 JSON
├── audio/            # 配音 MP3 + 时间线 JSON
├── images/           # 配图 PNG
├── subtitles/        # SRT 字幕 + 时间线 JSON
├── bgm/              # 背景音乐缓存
└── videos/           # 最终 MP4 视频
```

---

## 配置说明

编辑 `config.py` 可调整以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `VIDEO_WIDTH` / `HEIGHT` | 1080×1920 | 竖屏 9:16 |
| `VIDEO_FPS` | 30 | 帧率 |
| `KEN_BURNS_ZOOM_START/END` | 1.0 → 1.08 | 图片缩放范围 |
| `SUBTITLE_FONT_SIZE` | 48 | 字幕字号 |
| `MINIMAX_TTS_MODEL` | speech-02 | MiniMax TTS 模型 |
| `MINIMAX_TTS_VOICE_ID` | female-shaonv | 默认配音音色 |

---

## 视频规格

- **分辨率**：1080×1920（竖屏 9:16）
- **时长**：45-90 秒（由脚本决定）
- **编码**：H.264 + AAC
- **帧率**：30fps
- **字幕**：底部居中，半透明背景，白色字体 + 黑色描边

---

## 模块架构

```
input: topic
    │
    ▼
┌─────────────────┐
│ script_gen.py   │  DeepSeek → JSON 脚本
│ (DeepSeek API)  │  含旁白 + 画面提示 + BGM 风格
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ tts    │ │ image  │
│ .py    │ │ .py    │
│ MiniMax│ │ MiniMax│
│ /Edge  │ │ T2I    │
└──┬─────┘ └──┬─────┘
   │          │
   ▼          ▼
┌────────┐ ┌────────┐
│ audio  │ │ images │
│ .mp3   │ │ .png   │
└──┬─────┘ └──┬─────┘
   │          │
   ▼          ▼
┌─────────────────┐
│ subtitle_gen.py │  Whisper → SRT
│ (faster-whisper)│  或时间预估模式
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ video_comp.py   │  moviepy → MP4
│ (FFmpeg)        │  Ken Burns + 字幕 + BGM
└─────────────────┘
```

---

## 许可

本项目仅供学习和个人使用。使用第三方 API 时请遵守各平台的服务条款。
