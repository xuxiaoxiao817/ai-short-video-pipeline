# 用户操作手册

## AI 短视频自动生成系统

**文档版本**：v1.0  
**创建日期**：2026-05-24

---

## 1. 快速开始

### 1.1 环境准备

**系统要求**：
- Python 3.10 或更高版本
- 网络连接（用于 API 调用和模型下载）

### 1.2 安装步骤

```bash
# 1. 进入项目目录
cd dsp

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
```

### 1.3 编辑 .env 文件

用文本编辑器打开 `.env`，填入你的 API 密钥：

```ini
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
MINIMAX_API_KEY=sk-your-minimax-api-key
MINIMAX_GROUP_ID=your-minimax-group-id
```

**如何获取 API Key**：

| 服务 | 注册地址 | 操作步骤 |
|------|---------|---------|
| DeepSeek | https://platform.deepseek.com | 注册 → 创建 API Key |
| MiniMax | https://platform.minimaxi.com | 注册 → 订阅 Token Plan → 创建 API Key |

> MiniMax 采用 Token Plan 套餐制，订阅后即可使用文生图、TTS 等服务。

### 1.4 验证安装

```bash
# 检查 Python 版本
python --version

# 检查依赖是否安装完
python -c "from moviepy import ImageClip; print('moviepy OK')"
python -c "import edge_tts; print('edge-tts OK')"
```

---

## 2. 生成第一个视频

### 2.1 基础命令

```bash
python pipeline.py --topic "什么是量子纠缠？"
```

系统将依次执行以下步骤：

```
[AI] 正在调用 DeepSeek 生成脚本...
[OK] 脚本已生成: output/scripts/xxx.json
   标题: 量子纠缠之谜
   分镜数: 6

[NET] 尝试 MiniMax TTS...
[WARN] MiniMax TTS 余额不足，将自动切换到 Edge TTS 免费方案
[NET] 切换到 Edge TTS（免费）...
[AUDIO] 使用 Edge TTS 合成语音...
[OK] Edge TTS 成功: output/audio/xxx_full.mp3 (293.3 KB)

[IMAGE] 正在调用 MiniMax 文生图...
[OK] 图片已保存: output/images/xxx_scene_00_0.png

[NOTE] 阶段 4/5: 字幕生成
[OK] 字幕已生成: output/subtitles/xxx.srt (6 条)

[VIDEO] 阶段 5/5: 视频合成
正在渲染视频...
[OK] 视频合成完成！[FILE] output/videos/xxx.mp4
```

### 2.2 添加额外脚本要求

```bash
python pipeline.py --topic "黑洞" --prompt "用霍金辐射理论引入，30秒以内，5个分镜"
```

`--prompt` 参数的内容会追加到 LLM 的提示词中，用于控制脚本的风格、时长、结构等。

### 2.3 使用本地背景音乐

```bash
python pipeline.py --topic "相对论" --bgm "music/background.mp3"
```

支持的格式：MP3、WAV、FLAC、AAC。系统会自动循环或裁剪 BGM 以匹配视频长度，并做渐入渐出混音。

---

## 3. 进阶用法

### 3.1 跳过已完成的阶段

每个阶段的输出会缓存到 `output/` 目录。如果某个步骤之前已成功执行，可以跳过它：

```bash
# 只重新配图和合成视频（不重新生成脚本和配音）
python pipeline.py --topic "量子纠缠" --skip-script --skip-tts
```

可用跳过参数：

| 参数 | 作用 |
|------|------|
| `--skip-script` | 跳过脚本生成 |
| `--skip-tts` | 跳过配音合成 |
| `--skip-images` | 跳过配图生成 |
| `--skip-subtitles` | 跳过字幕生成 |

### 3.2 调整视频参数

编辑 `config.py` 可调整以下参数：

```python
# 视频分辨率（竖屏 9:16）
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

# Ken Burns 缩放范围
KEN_BURNS_ZOOM_START = 1.0    # 起始缩放
KEN_BURNS_ZOOM_END = 1.08     # 结束缩放（放大 8%）

# 字幕样式
SUBTITLE_FONT_SIZE = 48        # 字号
SUBTITLE_FONT_COLOR = "white"  # 字体颜色

# MiniMax TTS（如有余额）
MINIMAX_TTS_MODEL = "speech-02"
MINIMAX_TTS_VOICE_ID = "female-shaonv"
```

### 3.3 使用 Whisper 精确字幕

如果安装了 faster-whisper，系统会在首次运行时自动下载模型（约 150MB），之后使用 GPU（如有）或 CPU 进行精确的语音转文字：

```bash
# 确保已安装
pip install faster-whisper

# 然后正常运行即可，系统会自动使用 Whisper
python pipeline.py --topic "相对论"
```

> 如果网络无法访问 HuggingFace 下载模型，系统会自动回退到时间预估模式，不影响视频生成。

---

## 4. 使用场景示例

### 4.1 科技科普

```bash
python pipeline.py --topic "5G 和 4G 有什么区别？" --prompt "用比喻解释，通俗易懂"
```

### 4.2 历史人文

```bash
python pipeline.py --topic "为什么古埃及人建造金字塔？" --prompt "包含至少一个考古发现的故事"
```

### 4.3 医学健康

```bash
python pipeline.py --topic "疫苗的工作原理" --prompt "用军队比喻免疫系统"
```

### 4.4 批量生产

```bash
# 生成多个视频
for topic in "量子纠缠" "黑洞" "相对论" "基因编辑" "人工智能"; do
    python pipeline.py --topic "$topic"
done
```

---

## 5. 常见问题

### Q: 运行时提示 API Key 未配置

```
[WARN] 以下环境变量未设置: DEEPSEEK_API_KEY, MINIMAX_API_KEY
```

请检查 `.env` 文件是否存在且内容正确，确认环境变量名与模板一致。

### Q: MiniMax 文生图失败

检查 MiniMax 账户余额和 Token Plan 状态。文生图使用 `image-01` 模型，需确保 Token Plan 包含该服务。

### Q: 视频渲染非常慢

- 视频渲染是 CPU 密集型操作，5 个分镜约需 3-8 分钟
- 首次运行时 FFmpeg 首次加载可能稍慢
- 可以降低 `VIDEO_FPS` 或增大 `bitrate` 参数来压缩

### Q: 生成的视频没有字幕

字幕生成需要 Whisper 模型或时间预估模式：
- 如果 Whisper 无法下载，会自动使用预估模式（基于文本长度和音频时长估算）
- 确保音频文件正常生成（`output/audio/` 下有 `.mp3` 文件）

### Q: 如何更换配音音色？

编辑 `config.py` 中的 `MINIMAX_TTS_VOICE_ID`：
- `female-shaonv` — 标准女声（默认）
- `female-yuwei` — 温柔御姐音
- `male-haoqun` — 沉稳男声

Edge TTS 音色在 `tts_gen.py` 的 `_synthesize_edge()` 函数中修改 `voice` 参数：
- `zh-CN-XiaoxiaoNeural` — 标准女声
- `zh-CN-YunxiNeural` — 标准男声

---

## 6. 输出文件说明

运行完成后，所有输出文件位于 `output/` 目录：

```
output/
├── scripts/
│   └── {hash}.json              # 脚本 JSON（含标题、分镜、旁白、画面描述）
├── audio/
│   ├── {hash}_full.mp3          # 完整配音音频
│   └── {hash}_timeline.json     # 时间线
├── images/
│   ├── {hash}_scene_00_0.png    # 第 1 分镜配图
│   ├── {hash}_scene_01_0.png    # 第 2 分镜配图
│   └── ...                      # 依次类推
├── subtitles/
│   ├── {hash}.srt               # SRT 字幕文件
│   └── {hash}_timeline.json     # 字幕时间线
├── bgm/
│   └── {hash}_bgm.mp3           # 自动生成的 BGM（如启用）
└── videos/
    └── xxx.mp4                  # 最终视频
```

> `{hash}` 是由主题 MD5 的前 12 位生成，同一主题的运行会复用同 `{hash}` 的缓存文件。
