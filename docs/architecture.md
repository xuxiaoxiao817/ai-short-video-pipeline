# 系统架构设计文档

## AI 短视频自动生成系统

**文档版本**：v1.0  
**创建日期**：2026-05-24

---

## 1. 总体架构

本系统采用**管道-过滤器（Pipeline & Filter）**架构风格，将视频制作流程拆解为 5 个独立的处理阶段，每个阶段负责一个原子任务，通过标准化的数据格式进行衔接。

### 1.1 架构图

```
┌─────────────────────────────────────────────────────┐
│                  用户命令行接口                        │
│              pipeline.py --topic "主题"               │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                   管道编排层 (pipeline.py)             │
│    • 阶段调度     • 缓存管理     • 错误处理            │
│    • 进度日志     • 参数传递                          │
└──┬──────┬──────┬──────┬──────┬──────────────────────┘
   │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼
┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
│脚本  │ │配音  │ │配图  │ │字幕  │ │视频  │
│生成  │ │合成  │ │生成  │ │生成  │ │合成  │
├─────┤ ├─────┤ ├─────┤ ├─────┤ ├─────┤
│Deep │ │Mini │ │Mini │ │Whis │ │movi │
│Seek │ │Max  │ │Max  │ │per  │ │epy  │
│LLM  │ │TTS  │ │T2I  │ │ASR  │ │FFm- │
│     │ │Edge │ │     │ │预估 │ │peg  │
│     │ │TTS  │ │     │ │     │ │     │
└──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘
   │       │       │       │       │
   ▼       ▼       ▼       ▼       ▼
┌─────────────────────────────────────────────────────┐
│                   输出层 (output/)                    │
│  scripts/  audio/  images/  subtitles/  videos/      │
└─────────────────────────────────────────────────────┘
```

### 1.2 数据流

```
用户输入 (topic, prompt, bgm)
    │
    ├──→ script_gen.py →── JSON 脚本 ───────────────────┐
    │                                                    │
    ├──→ tts_gen.py    →── MP3 音频文件 ────────────────┐│
    │                                                    ││
    ├──→ image_gen.py  →── PNG 图片文件 ───────────────┐││
    │                                                    │││
    ├──→ subtitle_gen.py → SRT 字幕文件 + 时间线 JSON ┐│││
    │                                                    ││││
    └──→ video_comp.py  →── MP4 视频文件 ←──────────────┘│││
                                                          └┘││
                                                            └┘│
                                                              └┘
```

---

## 2. 模块设计

### 2.1 配置模块 (config.py)

**职责**：集中管理所有配置参数，从 `.env` 文件加载 API 密钥。

```
config.py
├── 路径常量（PROJECT_ROOT, OUTPUT_DIR, ...）
├── DeepSeek 配置（API Key, Base URL, Model）
├── MiniMax 配置（API Key, Group ID, 各服务端点）
├── 视频参数（分辨率、帧率、Ken Burns 缩放、字幕样式）
├── ensure_dirs() — 创建输出目录
└── validate_config() — 检查配置完整性
```

**设计要点**：所有输出路径由 `OUTPUT_DIR` 派生，确保单次运行输出集中。

### 2.2 工具模块 (utils.py)

**职责**：提供各模块通用的工具函数。

| 函数 | 说明 |
|------|------|
| `save_json()` | 保存 JSON 文件 |
| `load_json()` | 加载 JSON 文件 |
| `download_file()` | 下载远程文件到本地 |
| `make_minimax_headers()` | 构造 MiniMax API 请求头（含 Auth + Group ID） |
| `retry_on_failure()` | 错误重试工具（指数退避） |
| `format_timestamp()` | 秒数 → SRT 时间戳格式 |
| `slugify()` | 主题 → 安全的文件名校验和前缀 |

### 2.3 脚本生成 (script_gen.py)

**职责**：调用 DeepSeek API 生成结构化短视频脚本。

```
输入: topic (str), custom_prompt (Optional[str])
输出: dict { title, bgm_style, scenes: [{narration, image_prompt, keywords}], outro_text }
```

**关键设计**：
- 使用 OpenAI 兼容客户端访问 DeepSeek
- System Prompt 严格定义输出 JSON 格式
- 对 LLM 输出做格式清洗（移除 markdown 代码块标记）
- 结果缓存到 `output/scripts/{slug}.json`

### 2.4 配音合成 (tts_gen.py)

**职责**：将脚本旁白合成为自然语音，自动选择最优 TTS 方案。

```
输入: script (dict), topic (str)
输出: audio_path (Path)
```

**TTS 选择策略**：
1. 尝试 MiniMax Speech-02（高质量，需账户余额）
2. 若余额不足 → 自动切换到 Edge TTS（免费）
3. 若都失败 → 返回 None，管道报错

**设计要点**：
- 全文合成模式：所有旁白拼接后一次 TTS 调用
- 时间线保存：输出音频的同时保存 `{slug}_timeline.json`，供字幕和视频合成使用

### 2.5 图片生成 (image_gen.py)

**职责**：调用 MiniMax 文生图 API，为每个分镜生成配图。

```
输入: script (dict), topic (str), aspect_ratio (str)
输出: [{index, prompt, narration, image_paths}]
```

**设计要点**：
- 每个分镜独立调用 API（间隔 1 秒防限流）
- 返回结果解析兼容 MiniMax 的 `{data: {image_urls: [...]}}` 格式
- 自动重试（3 次，含指数退避）
- 图片缓存到 `output/images/`

### 2.6 字幕生成 (subtitle_gen.py)

**职责**：对配音音频做语音识别，生成 SRT 字幕文件和分段时间线。

```
输入: audio_path (Path), script (dict), topic (str)
输出: (srt_path, timeline)
```

**ASR 策略**：
1. 优先：faster-whisper（本地模型，精确时间戳）
2. 回退：_estimate_timeline（按文本长度比例分配时间，无网络/GPU 依赖）

**SRT 格式**：
```
1
00:00:00,000 --> 00:00:02,500
旁白文本第一句

2
00:00:02,500 --> 00:00:05,000
旁白文本第二句
```

### 2.7 视频合成 (video_comp.py)

**职责**：将所有素材合成为最终视频，是系统中最复杂的模块。

```
输入: script, image_paths, audio_path, srt_path, timeline, topic, bgm_path
输出: output_path (Path)
```

**合成步骤**：
1. 加载配音音频，获取总时长
2. 解析 SRT 字幕文件为时间分段
3. 为每个分镜创建带 Ken Burns 动效的 ImageClip
4. 叠加字幕（PIL 渲染，不依赖 ImageMagick）
5. 添加开场标题画面和片尾引导画面
6. 混音：配音 + BGM（自动循环/裁剪、渐入渐出）
7. 调用 FFmpeg（通过 moviepy）渲染最终视频

**Ken Burns 动效实现**：
```
每张图片从 start_scale (1.0) 缓慢缩放到 end_scale (1.08)
使用 time-varying lambda 实现连续缩放
保持画面居中裁剪，适配 9:16 目标尺寸
```

---

## 3. 关键技术决策

### 3.1 为什么用 PIL 渲染字幕而不是 TextClip？

moviepy 的 `TextClip` 在 Windows 上依赖 ImageMagick，增加部署复杂度。改用 PIL 直接渲染字幕帧为 RGBA 数组，再转为 `ImageClip`，消除了外部依赖。

### 3.2 为什么 TTS 设计为双方案？

MiniMax TTS 质量高但需付费且可能余额不足，Edge TTS 免费无限制。双方案设计让系统在无成本的基础设施上也能运行，余额充足时自动享受高质量。

### 3.3 为什么字幕 Whisper 和预估共存？

Whisper 本地模型需要 GPU 加速以获得实时性能，且首次需要下载模型（~150MB）。预估模式仅依赖文本长度和音频时长，零资源消耗，适合开发调试和低配环境。

---

## 4. 异常处理策略

| 异常类型 | 处理方式 |
|---------|---------|
| API 调用失败（网络/超时） | 自动重试 3 次（指数退避 2s, 4s, 8s） |
| API 余额不足 | 闭环检测，自动切换免费方案 |
| 图片生成失败 | 跳过该分镜图片，使用上一帧/纯色背景 |
| Whisper 模型下载失败 | 自动切换到时间预估模式 |
| FFmpeg 渲染失败 | 抛出异常，打印完整 traceback |

---

## 5. 目录结构

```
dsp/
├── config.py              # 配置管理
├── utils.py               # 工具函数
├── script_gen.py          # 脚本生成
├── tts_gen.py             # 配音合成
├── image_gen.py           # 图片生成
├── subtitle_gen.py        # 字幕生成
├── video_comp.py          # 视频合成
├── pipeline.py            # 管道编排
├── requirements.txt       # 依赖清单
├── .env.example           # 环境变量模板
├── .gitignore
├── README.md
└── docs/
    ├── requirements-spec.md   # 需求规格说明书
    ├── architecture.md        # 本文件
    ├── usage-guide.md         # 用户操作手册
    └── developer-guide.md     # 开发者指南
└── output/
    ├── scripts/
    ├── audio/
    ├── images/
    ├── subtitles/
    ├── bgm/
    └── videos/
```
