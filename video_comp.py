"""
视频合成模块 - 使用 moviepy 将图片、音频、字幕合成为最终视频

核心功能：
1. Ken Burns 动效（图片缓慢缩放）
2. 字幕叠加（底部居中，背景半透明）
3. 配音 + BGM 混音
4. 分镜转场
"""

import json
from pathlib import Path
from typing import Optional

# moviepy core
try:
    from moviepy import (
        VideoFileClip, ImageClip, AudioFileClip, TextClip,
        CompositeVideoClip, concatenate_videoclips,
    )
    MOVIEPY_V2 = True
except ImportError:
    from moviepy.editor import (
        VideoFileClip, ImageClip, AudioFileClip, TextClip,
        CompositeVideoClip, concatenate_videoclips,
    )
    MOVIEPY_V2 = False

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    KEN_BURNS_ZOOM_START, KEN_BURNS_ZOOM_END,
    SUBTITLE_FONT_SIZE, SUBTITLE_FONT_COLOR, SUBTITLE_BG_COLOR,
    VIDEO_DIR, BGM_DIR, SCRIPT_DIR, AUDIO_DIR, IMAGE_DIR, SUBTITLE_DIR,
)
from utils import slugify


# ============================================================
# 工具函数
# ============================================================

def _find_font(size: int = 48) -> Optional[str]:
    """查找系统中可用的中文字体"""
    import os
    # Windows 常见中文字体路径
    font_candidates = [
        # Windows
        "C:/Windows/Fonts/msyh.ttc",          # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",        # 黑体
        "C:/Windows/Fonts/simsun.ttc",        # 宋体
        "C:/Windows/Fonts/STHeiti.ttf",       # 华文黑体
        "C:/Windows/Fonts/msyhbd.ttc",        # 微软雅黑粗体
        # Linux / macOS
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            return path
    return None


def _render_subtitle_frame(
    text: str,
    width: int = VIDEO_WIDTH,
    height: int = 120,
    font_size: int = SUBTITLE_FONT_SIZE,
    font_color: str = "white",
    bg_color: tuple = (0, 0, 0, 160),
) -> np.ndarray:
    """
    用 PIL 渲染一个字幕帧，返回 numpy array (HWC, RGBA)

    Args:
        text: 字幕文本
        width: 字幕图片宽度
        height: 字幕图片高度
        font_size: 字号
        font_color: 字体颜色
        bg_color: 背景色 (RGBA)

    Returns:
        numpy array 格式的 RGBA 图像
    """
    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font_path = _find_font(font_size)
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    # 计算文本位置（居中）
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2 - 5

    # 描边效果（黑色描边，提升可读性）
    stroke_color = (0, 0, 0, 200)
    for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (0, -2), (0, 2), (-2, 0), (2, 0)]:
        draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
    draw.text((x, y), text, font=font, fill=font_color)

    return np.array(img)


def _make_subtitle_clip_pil(
    text: str,
    start: float,
    end: float,
    video_size: tuple = (VIDEO_WIDTH, VIDEO_HEIGHT),
) -> "ImageClip":
    """
    用 PIL 生成字幕 ImageClip

    Args:
        text: 字幕文本
        start: 开始时间（秒）
        end: 结束时间（秒）
        video_size: 视频尺寸 (w, h)

    Returns:
        ImageClip 对象（带透明通道）
    """
    bar_height = 130
    bar_img = _render_subtitle_frame(
        text=text,
        width=video_size[0],
        height=bar_height,
    )

    # 转为 moviepy ImageClip
    clip = ImageClip(bar_img, is_mask=False, duration=end - start)
    clip = clip.with_start(start).with_duration(end - start)

    # 定位到底部居中
    bottom_margin = 80
    pos_x = 0  # 全宽
    pos_y = video_size[1] - bar_height - bottom_margin
    clip = clip.with_position((pos_x, pos_y))

    return clip


def _parse_srt(srt_path: Path) -> list[dict]:
    """
    解析 SRT 字幕文件为分段列表

    Returns:
        [{index, start, end, text}, ...]
    """
    if not srt_path.exists():
        return []

    content = srt_path.read_text(encoding="utf-8")
    blocks = content.strip().split("\n\n")

    segments = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0].strip())
            time_line = lines[1].strip()
            # 解析时间戳: 00:00:01,500 --> 00:00:04,000
            parts = time_line.split(" --> ")
            start = _parse_srt_time(parts[0])
            end = _parse_srt_time(parts[1])
            text = "".join(lines[2:]).strip()
            segments.append({
                "index": index,
                "start": start,
                "end": end,
                "text": text,
            })
        except (ValueError, IndexError):
            continue

    return segments


def _parse_srt_time(ts: str) -> float:
    """解析 SRT 时间戳为秒数"""
    # 格式: HH:MM:SS,mmm
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


# ============================================================
# Ken Burns 动效
# ============================================================

def _ken_burns_clip(
    image_path: str,
    duration: float,
    start_scale: float = KEN_BURNS_ZOOM_START,
    end_scale: float = KEN_BURNS_ZOOM_END,
    target_size: tuple = (VIDEO_WIDTH, VIDEO_HEIGHT),
) -> ImageClip:
    """
    创建带 Ken Burns 缩放动效的图片剪辑

    从 start_scale 缓慢缩放到 end_scale，同时保持居中裁剪
    """
    clip = ImageClip(image_path, duration=duration)

    # 先缩放到覆盖目标尺寸的最小比例
    img_w, img_h = clip.size
    scale_w = target_size[0] / img_w
    scale_h = target_size[1] / img_h
    cover_scale = max(scale_w, scale_h) * start_scale

    clip = clip.resized(cover_scale)
    clip = clip.with_duration(duration)

    # 应用 Ken Burns 随时间缩放
    # 用 time_transform 实现连续缩放
    def resize_func(t):
        progress = t / duration if duration > 0 else 0
        current_scale = start_scale + (end_scale - start_scale) * progress
        # 用 current_scale 乘以 cover_scale 得到总缩放
        total_scale = cover_scale * (current_scale / start_scale)
        # 返回缩放后的尺寸
        new_w = int(img_w * total_scale)
        new_h = int(img_h * total_scale)
        return new_w, new_h

    # 使用 ImageClip 的 resize lambda
    clip = clip.resized(resize_func)

    # 居中裁剪到目标尺寸
    clip = clip.with_position(("center", "center"))
    # 使用 crop 确保正好目标尺寸
    clip = clip.with_effects([
        vfx_crop(x1=0, y1=0, width=target_size[0], height=target_size[1])
    ]) if MOVIEPY_V2 else clip

    return clip


def vfx_crop(x1=0, y1=0, width=None, height=None):
    """创建一个裁剪效果函数（兼容 v1/v2）"""
    def crop_effect(clip):
        if MOVIEPY_V2:
            from moviepy import vfx
            return clip.with_effects([vfx.Crop(
                x1=x1, y1=y1,
                x2=x1 + width, y2=y1 + height,
            )])
        else:
            return clip.crop(x1=x1, y1=y1,
                             width=width, height=height)
    return crop_effect


# ============================================================
# 主合成函数
# ============================================================

def compose_video(
    script: dict,
    image_paths: list[str],
    audio_path: str,
    srt_path: str,
    timeline: list[dict],
    topic: str,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.15,
    output_path: Optional[Path] = None,
) -> Path:
    """
    合成最终视频

    Args:
        script: 脚本 dict
        image_paths: 图片路径列表（与分镜对应）
        audio_path: 配音音频路径
        srt_path: SRT 字幕文件路径
        timeline: 时间线 [{index, start, end, duration}]
        topic: 主题
        bgm_path: 可选背景音乐路径
        bgm_volume: BGM 音量 (0-1)
        output_path: 输出路径

    Returns:
        输出视频文件路径
    """
    safe_name = slugify(topic)
    if output_path is None:
        output_path = VIDEO_DIR / f"{safe_name}.mp4"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------
    # 1. 加载配音音频
    # -----------------------------------------------------------
    print(f"[VIDEO] 开始合成视频...")
    audio_clip = AudioFileClip(audio_path)
    total_duration = audio_clip.duration
    print(f"   音频时长: {total_duration:.1f}s")

    # -----------------------------------------------------------
    # 2. 加载字幕
    # -----------------------------------------------------------
    subtitle_segments = _parse_srt(Path(srt_path))
    if not subtitle_segments and timeline:
        # 如果没有 SRT（缺少 Whisper），从时间线构造
        subtitle_segments = [
            {"start": item["start"], "end": item["end"],
             "text": item["narration"], "index": i}
            for i, item in enumerate(timeline)
        ]
    print(f"   字幕段落: {len(subtitle_segments)} 条")

    # -----------------------------------------------------------
    # 3. 创建分镜片段
    # -----------------------------------------------------------
    scene_clips = []
    for i, scene_tl in enumerate(timeline):
        scene_idx = scene_tl["index"]
        start_time = scene_tl["start"]
        end_time = scene_tl["end"]
        duration = scene_tl.get("duration", end_time - start_time)

        if duration <= 0:
            duration = 3.0  # 兜底

        # 获取对应图片
        img_path = None
        if scene_idx < len(image_paths):
            img_path = image_paths[scene_idx]
        elif image_paths:
            img_path = image_paths[-1]  # 用最后一张
        else:
            # 无图片时创建一个纯色背景
            bg = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT),
                          (20, 30, 50))
            bg_path = Path(f"/tmp/fallback_bg_{i}.png")
            bg.save(bg_path)
            img_path = str(bg_path)

        # 创建 Ken Burns 动效片段
        try:
            scene_clip = _ken_burns_clip(
                img_path, duration=duration,
                target_size=(VIDEO_WIDTH, VIDEO_HEIGHT),
            )
            scene_clip = scene_clip.with_start(start_time)
            scene_clips.append(scene_clip)
        except Exception as e:
            print(f"[WARN]  分镜 {i} 动效失败: {e}")
            # 兜底：无动效
            fallback = ImageClip(img_path, duration=duration)
            fallback = fallback.resized(height=VIDEO_HEIGHT)
            fallback = fallback.with_position(("center", "center"))
            fallback = fallback.with_start(start_time)
            scene_clips.append(fallback)

        # 分镜间过渡的淡入淡出（通过只对第一个和最后一个做处理）
        if MOVIEPY_V2:
            try:
                from moviepy import vfx
                scene_clips[-1] = scene_clips[-1].with_effects([
                    vfx.FadeIn(0.3),
                    vfx.FadeOut(0.3),
                ])
            except ImportError:
                pass

    # -----------------------------------------------------------
    # 4. 合成视频轨道（图片 + 字幕）
    # -----------------------------------------------------------
    print(f"   正在合成视频轨道...")
    video_track = CompositeVideoClip(
        scene_clips,
        size=(VIDEO_WIDTH, VIDEO_HEIGHT),
    )

    # 添加字幕
    subtitle_clips = []
    for seg in subtitle_segments:
        if seg["text"]:
            try:
                sub_clip = _make_subtitle_clip_pil(
                    text=seg["text"],
                    start=seg["start"],
                    end=seg["end"],
                    video_size=(VIDEO_WIDTH, VIDEO_HEIGHT),
                )
                subtitle_clips.append(sub_clip)
            except Exception as e:
                print(f"[WARN]  字幕 '{seg['text'][:20]}...' 渲染失败: {e}")

    # 叠加字幕到视频
    if subtitle_clips:
        all_clips = [video_track] + subtitle_clips
        video_track = CompositeVideoClip(all_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))

    # -----------------------------------------------------------
    # 5. 添加开场标题
    # -----------------------------------------------------------
    title = script.get("title", "")
    outro = script.get("outro_text", "")
    title_clips = []

    if title:
        # 开场标题：前 2 秒
        title_img = _render_title_frame(title, VIDEO_WIDTH, VIDEO_HEIGHT)
        title_clip = ImageClip(title_img, is_mask=False, duration=2.5)
        title_clip = title_clip.with_start(0)
        if MOVIEPY_V2:
            try:
                from moviepy import vfx
                title_clip = title_clip.with_effects([vfx.FadeOut(0.5)])
            except ImportError:
                pass
        title_clips.append(title_clip)

    # 片尾文字（最后 3 秒）
    if outro:
        outro_img = _render_outro_frame(outro, VIDEO_WIDTH, VIDEO_HEIGHT)
        outro_duration = 3.0
        outro_start = max(0, total_duration - outro_duration)
        outro_clip = ImageClip(outro_img, is_mask=False, duration=outro_duration)
        outro_clip = outro_clip.with_start(outro_start)
        if MOVIEPY_V2:
            try:
                from moviepy import vfx
                outro_clip = outro_clip.with_effects([vfx.FadeIn(0.5)])
            except ImportError:
                pass
        title_clips.append(outro_clip)

    if title_clips:
        all_clips = [video_track] + title_clips
        video_track = CompositeVideoClip(all_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))

    # -----------------------------------------------------------
    # 6. 混音处理（配音 + BGM）
    # -----------------------------------------------------------
    # 先设置配音
    video_track = video_track.with_audio(audio_clip)

    # 加入 BGM
    if bgm_path and Path(bgm_path).exists():
        print(f"   添加背景音乐...")
        bgm_clip = AudioFileClip(str(bgm_path))

        from moviepy.audio.AudioClip import concatenate_audioclips
        from moviepy.audio.AudioClip import CompositeAudioClip

        # 循环或裁剪到视频长度
        if bgm_clip.duration < total_duration:
            loops = int(total_duration / bgm_clip.duration) + 1
            bgm_clip = concatenate_audioclips([bgm_clip] * loops)
        bgm_clip = bgm_clip.subclip(0, total_duration)

        # 渐入渐出
        try:
            from moviepy import vfx
            bgm_clip = bgm_clip.with_effects([
                vfx.AudioFadeIn(1.5),
                vfx.AudioFadeOut(3.0),
            ])
        except ImportError:
            from moviepy.audio.fx.all import audio_fadein, audio_fadeout
            bgm_clip = audio_fadein(bgm_clip, 1.5)
            bgm_clip = audio_fadeout(bgm_clip, 3.0)

        # 调整音量
        if MOVIEPY_V2:
            bgm_clip = bgm_clip.with_volume(bgm_volume)
        else:
            bgm_clip = bgm_clip.volumex(bgm_volume)

        # 混音
        final_audio = CompositeAudioClip([audio_clip, bgm_clip])
        video_track = video_track.with_audio(final_audio)
        print(f"   BGM 已加载: {Path(bgm_path).name}")

    # -----------------------------------------------------------
    # 8. 输出
    # -----------------------------------------------------------
    print(f"   正在渲染视频（这可能需要几分钟）...")
    print(f"   输出: {output_path}")
    print(f"   分辨率: {VIDEO_WIDTH}x{VIDEO_HEIGHT}, FPS: {VIDEO_FPS}")

    video_track.write_videofile(
        str(output_path),
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        threads=2,
        preset="medium",
        bitrate="5000k",
    )

    print(f"[OK] 视频合成完成！")
    print(f"   [FILE] {output_path}")

    return output_path


# ============================================================
# 开场/片尾画面
# ============================================================

def _render_title_frame(
    title: str,
    width: int,
    height: int,
) -> np.ndarray:
    """渲染开场标题画面"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # 深色半透明背景叠加
    overlay = Image.new("RGBA", (width, height), (10, 15, 30, 200))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    font_path = _find_font(72)
    if font_path:
        title_font = ImageFont.truetype(font_path, 72)
        sub_font = ImageFont.truetype(font_path, 36)
    else:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    # 标题居中
    subtitle_text = "知识科普"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    sub_bbox = draw.textbbox((0, 0), subtitle_text, font=sub_font)

    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    sub_w = sub_bbox[2] - sub_bbox[0]

    cx = width // 2
    cy = height // 2 - 40

    # 副标题（上方）
    draw.text((cx - sub_w // 2, cy - 80), subtitle_text,
              font=sub_font, fill=(180, 190, 255))

    # 主标题（白色）
    draw.text((cx - title_w // 2, cy), title,
              font=title_font, fill=(255, 255, 255))

    # 底部装饰线
    line_y = cy + title_h + 20
    draw.rectangle([cx - 60, line_y, cx + 60, line_y + 3], fill=(100, 140, 255))

    return np.array(img)


def _render_outro_frame(
    text: str,
    width: int,
    height: int,
) -> np.ndarray:
    """渲染片尾引导关注画面"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # 深色背景
    overlay = Image.new("RGBA", (width, height), (10, 15, 30, 220))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    font_path = _find_font(52)
    if font_path:
        font = ImageFont.truetype(font_path, 52)
        small_font = ImageFont.truetype(font_path, 32)
    else:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    cx = width // 2
    cy = height // 2

    draw.text((cx - tw // 2, cy - 40), text, font=font, fill=(255, 255, 255))

    # 提示关注
    follow_text = "点赞 · 关注 · 转发"
    fb = draw.textbbox((0, 0), follow_text, font=small_font)
    fw = fb[2] - fb[0]
    draw.text((cx - fw // 2, cy + 40), follow_text,
              font=small_font, fill=(180, 190, 255))

    return np.array(img)


# ============================================================
# 高级接口
# ============================================================

def compose_from_pipeline_data(
    script: dict,
    image_dir: Path,
    audio_path: Path,
    subtitle_dir: Path,
    topic: str,
    bgm_path: Optional[Path] = None,
) -> Path:
    """
    从 pipeline 生成的中间文件合成视频

    Args:
        script: 脚本 dict
        image_dir: 图片目录（内含 scene_xx.png 文件）
        audio_path: 配音音频路径
        subtitle_dir: 字幕目录（内含 .srt 和 _timeline.json 文件）
        topic: 主题
        bgm_path: 可选 BGM 路径

    Returns:
        视频输出路径
    """
    safe_name = slugify(topic)

    # 获取图片路径列表（按分镜索引排序）
    image_paths = sorted(
        [str(p) for p in image_dir.glob(f"{safe_name}_scene_*.png")],
        key=lambda x: int(x.split("_scene_")[1].split(".")[0])
    )
    if not image_paths:
        # 尝试匹配任意 png
        image_paths = sorted(
            [str(p) for p in image_dir.glob("*.png")],
        )
    print(f"   找到图片: {len(image_paths)} 张")

    # 获取字幕文件
    srt_path = subtitle_dir / f"{safe_name}.srt"
    if not srt_path.exists():
        srt_files = list(subtitle_dir.glob("*.srt"))
        srt_path = srt_files[0] if srt_files else subtitle_dir / "subtitles.srt"

    # 获取时间线
    timeline_path = subtitle_dir / f"{safe_name}_timeline.json"
    timeline = []
    if timeline_path.exists():
        data = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline = data.get("timeline", data.get("segments", []))

    return compose_video(
        script=script,
        image_paths=image_paths,
        audio_path=str(audio_path),
        srt_path=str(srt_path),
        timeline=timeline,
        topic=topic,
        bgm_path=str(bgm_path) if bgm_path else None,
    )


if __name__ == "__main__":
    # 测试（需要 mock 数据）
    print("视频合成模块加载成功")
    print(f"  moviepy v2: {MOVIEPY_V2}")
    print(f"  视频尺寸: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
    print(f"  中文字体: {_find_font()}")
