"""阶段4: MoviePy 视频合成（配图 + Ken Burns + 旁白 + BGM + 硬字幕 + 进度条）"""
from pathlib import Path

import numpy as np
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    VideoClip,
    concatenate_videoclips,
    vfx,
)
from PIL import Image, ImageDraw, ImageFont

import proglog

from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    BG_MUSIC_VOLUME, NARRATION_VOLUME,
    KB_ZOOM_START, KB_ZOOM_END,
    PROGRESS_BAR_HEIGHT, PROGRESS_BAR_Y,
    PROGRESS_BAR_BG, PROGRESS_BAR_FG,
    SUBTITLE_FONT_SIZE, SUBTITLE_FONT_COLOR,
    SUBTITLE_STROKE_COLOR, SUBTITLE_STROKE_WIDTH,
    SUBTITLE_Y, SUBTITLE_MAX_CHARS,
    FONT_PATH, SLIDE_TRANSITION_DURATION,
)


# ── 渲染进度 Logger（proglog 接口，转发给 Streamlit） ──


class _StreamlitProgressLogger(proglog.ProgressBarLogger):
    """将 MoviePy 内部 tqdm 进度转发给 progress_callback。"""

    def __init__(self, progress_callback, start_pct=0.7, end_pct=1.0):
        super().__init__()
        self._cb = progress_callback
        self._start = start_pct
        self._end = end_pct

    def bars_callback(self, bar, attr, value, old_value):
        if attr == "index" and self._cb:
            total = self.bars.get(bar, {}).get("total", 0)
            if total and total > 0:
                pct = min(value / total, 1.0)
                mapped = self._start + pct * (self._end - self._start)
                self._cb(mapped, f"渲染中 {int(pct * 100)}%...")


# ── 字幕工具函数 ──


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """将文本按字数拆行（中文无空格断行）。"""
    lines = []
    for i in range(0, len(text), max_chars):
        lines.append(text[i:i + max_chars])
    return lines


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """加载中文字体，失败回退默认。"""
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except Exception:
        return ImageFont.load_default()


def _build_subtitle_data(segments: list[dict], durations: list[float]) -> list[dict]:
    """根据段落文本和音频时长，构建字幕时间轴。

    Returns:
        [{"text": str, "start": float, "end": float}, ...]
    """
    subs = []
    current_time = 0.0
    for seg, dur in zip(segments, durations):
        text = seg.get("narration_text", "").strip()
        if not text:
            current_time += dur
            continue
        # 音频实际时长（去掉 0.5s padding）
        audio_dur = max(dur - 0.5, 1.0)
        subs.append({
            "text": text,
            "start": current_time,
            "end": current_time + audio_dur,
        })
        current_time += dur
    return subs


# ── Ken Burns + 进度条 + 字幕 ──


def _ken_burns_clip(image_path: str, duration: float, reverse: bool = False,
                    total_duration: float = 0, start_time: float = 0,
                    subtitles: list[dict] = None, font: ImageFont.FreeTypeFont = None) -> VideoClip:
    """用 PIL + numpy 逐帧生成 Ken Burns 缩放 + 底部进度条 + 硬字幕。

    Args:
        image_path: 预处理后的配图路径
        duration: 片段时长（秒）
        reverse: True 则从放大缩回原始，False 则从原始放大
        total_duration: 视频总时长（秒），用于计算进度
        start_time: 本片段在视频中的起始时间（秒）
        subtitles: 全局字幕时间轴
        font: PIL 字体对象
    """
    img = Image.open(image_path).convert("RGB")
    img_w, img_h = img.size

    # 预计算进度条 alpha 混合系数
    bg_alpha = PROGRESS_BAR_BG[3] / 255.0
    fg_alpha = PROGRESS_BAR_FG[3] / 255.0
    bar_y = PROGRESS_BAR_Y
    bar_h = PROGRESS_BAR_HEIGHT

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        # Ken Burns 缩放插值
        if reverse:
            zoom = KB_ZOOM_END + (KB_ZOOM_START - KB_ZOOM_END) * progress
        else:
            zoom = KB_ZOOM_START + (KB_ZOOM_END - KB_ZOOM_START) * progress
        # 中心裁剪
        crop_w = int(VIDEO_WIDTH / zoom)
        crop_h = int(VIDEO_HEIGHT / zoom)
        left = (img_w - crop_w) // 2
        top = (img_h - crop_h) // 2
        cropped = img.crop((left, top, left + crop_w, top + crop_h))
        pil_frame = cropped.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)

        # ── 绘制硬字幕（用 PIL 以利用字体描边） ──
        if subtitles and font:
            global_t = start_time + t
            current_sub = None
            for sub in subtitles:
                if sub["start"] <= global_t <= sub["end"]:
                    current_sub = sub
                    break
            if current_sub:
                draw = ImageDraw.Draw(pil_frame)
                lines = _wrap_text(current_sub["text"], SUBTITLE_MAX_CHARS)
                # 从最后一行往上排列
                line_height = SUBTITLE_FONT_SIZE + 8
                total_text_h = len(lines) * line_height
                y_start = SUBTITLE_Y - total_text_h // 2
                for li, line in enumerate(lines):
                    bbox = draw.textbbox((0, 0), line, font=font)
                    tw = bbox[2] - bbox[0]
                    x = (VIDEO_WIDTH - tw) // 2
                    y = y_start + li * line_height
                    draw.text(
                        (x, y), line, font=font,
                        fill=SUBTITLE_FONT_COLOR,
                        stroke_width=SUBTITLE_STROKE_WIDTH,
                        stroke_fill=SUBTITLE_STROKE_COLOR,
                    )

        frame = np.array(pil_frame)

        # ── 绘制进度条 ──
        if total_duration > 0:
            global_t = start_time + t
            pct = min(global_t / total_duration, 1.0)
            bar_end = int(VIDEO_WIDTH * pct)

            # 底色轨道
            bg_rgb = PROGRESS_BAR_BG[:3]
            frame[bar_y:bar_y + bar_h, :] = (
                frame[bar_y:bar_y + bar_h, :] * (1 - bg_alpha)
                + np.array(bg_rgb) * bg_alpha
            ).astype(np.uint8)

            # 已播放填充
            if bar_end > 0:
                fg_rgb = PROGRESS_BAR_FG[:3]
                frame[bar_y:bar_y + bar_h, :bar_end] = (
                    frame[bar_y:bar_y + bar_h, :bar_end] * (1 - fg_alpha)
                    + np.array(fg_rgb) * fg_alpha
                ).astype(np.uint8)

        return frame

    return VideoClip(make_frame, duration=duration)


# ── 图片预处理 ──


def _prepare_image(image_path: Path) -> str:
    """将配图 resize 到视频尺寸，留出 Ken Burns 缩放余量。"""
    img = Image.open(str(image_path))
    zoom = max(KB_ZOOM_START, KB_ZOOM_END)
    target_w = int(VIDEO_WIDTH * zoom)
    target_h = int(VIDEO_HEIGHT * zoom)
    img = img.resize((target_w, target_h), Image.LANCZOS)
    prepared_path = image_path.with_stem(image_path.stem + "_prepared")
    img.save(str(prepared_path))
    return str(prepared_path)


# ── 主入口 ──


def compose_video(
    image_path: Path,
    audio_paths: list[Path],
    output_path: Path,
    segments: list[dict] = None,
    bg_music_path: Path = None,
    progress_callback=None,
) -> Path:
    """
    合成视频: 1张配图 + 多段旁白 + 可选BGM + 硬字幕 + 进度条

    Args:
        image_path: 选定的配图路径
        audio_paths: 旁白音频路径列表
        output_path: 输出视频路径
        segments: 脚本段落（含 narration_text，用于硬字幕）
        bg_music_path: 背景音乐路径（可选）
        progress_callback: 进度回调 (pct: float, msg: str)

    Returns:
        生成的视频路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prepared_image = _prepare_image(image_path)

    clips = []
    total = len(audio_paths)

    # 第一遍：加载音频，计算各段时长和总时长
    audio_clips = []
    durations = []
    for i, audio_path in enumerate(audio_paths):
        if progress_callback:
            progress_callback(i / total * 0.3, f"加载音频 {i+1}/{total}...")
        audio_clip = AudioFileClip(str(audio_path))
        duration = audio_clip.duration + 0.5  # padding
        audio_clips.append(audio_clip)
        durations.append(duration)

    total_duration = sum(durations)

    # 构建字幕时间轴
    subtitles = []
    if segments:
        subtitles = _build_subtitle_data(segments, durations)
    font = _load_font(SUBTITLE_FONT_SIZE) if subtitles else None

    # 第二遍：生成 Ken Burns 片段（含进度条 + 硬字幕）
    start_time = 0.0
    for i, (audio_clip, duration) in enumerate(zip(audio_clips, durations)):
        if progress_callback:
            progress_callback(0.3 + i / total * 0.2, f"生成片段 {i+1}/{total}...")

        img_clip = _ken_burns_clip(
            prepared_image, duration, reverse=(i % 2 == 1),
            total_duration=total_duration, start_time=start_time,
            subtitles=subtitles, font=font,
        ).set_audio(audio_clip)
        clips.append(img_clip)
        start_time += duration

    if progress_callback:
        progress_callback(0.5, "拼接片段...")

    final_video = concatenate_videoclips(clips, method="compose")

    # 混合 BGM
    if bg_music_path and bg_music_path.exists():
        if progress_callback:
            progress_callback(0.6, "混合背景音乐...")
        try:
            bg_music = AudioFileClip(str(bg_music_path)).volumex(BG_MUSIC_VOLUME)
            if bg_music.duration < final_video.duration:
                bg_music = bg_music.fx(vfx.loop, duration=final_video.duration)
            else:
                bg_music = bg_music.subclip(0, final_video.duration)

            composite_audio = CompositeAudioClip([
                final_video.audio.volumex(NARRATION_VOLUME),
                bg_music,
            ])
            final_video = final_video.set_audio(composite_audio)
        except Exception as e:
            print(f"BGM 混合失败，使用纯旁白: {e}")

    if progress_callback:
        progress_callback(0.7, f"开始渲染（约 {final_video.duration:.0f} 秒视频）...")

    # 自定义 logger 转发渲染进度给 Streamlit
    render_logger = _StreamlitProgressLogger(progress_callback, 0.7, 1.0)

    final_video.write_videofile(
        str(output_path),
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="ultrafast",
        threads=4,
        logger=render_logger,
    )

    if progress_callback:
        progress_callback(1.0, "视频合成完成")

    # 清理临时文件
    try:
        Path(prepared_image).unlink(missing_ok=True)
    except Exception:
        pass

    return output_path


# ── PPT 多幻灯片合成 ──


def compose_ppt_video(
    slide_images: list[Path],
    audio_paths: list[Path],
    output_path: Path,
    segments: list[dict] = None,
    slide_segment_map: dict = None,
    bg_music_path: Path = None,
    progress_callback=None,
) -> Path:
    """
    PPT 模式视频合成: 多张幻灯片 + Ken Burns + 交叉淡入淡出 + 旁白 + BGM + 硬字幕 + 进度条

    Args:
        slide_images: 幻灯片图片路径列表（按 slide id 顺序）
        audio_paths: 旁白音频路径列表（按 segment id 顺序）
        output_path: 输出视频路径
        segments: 脚本段落列表（含 narration_text，用于硬字幕）
        slide_segment_map: {slide_id: [seg_id, ...]} 映射
        bg_music_path: 背景音乐路径（可选）
        progress_callback: 进度回调 (pct: float, msg: str)

    Returns:
        生成的视频路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── 1. 加载所有音频，计算各段时长 ──
    audio_clips = []
    seg_durations = []
    total_segs = len(audio_paths)

    for i, audio_path in enumerate(audio_paths):
        if progress_callback:
            progress_callback(i / total_segs * 0.2, f"加载音频 {i+1}/{total_segs}...")
        audio_clip = AudioFileClip(str(audio_path))
        duration = audio_clip.duration + 0.5  # padding
        audio_clips.append(audio_clip)
        seg_durations.append(duration)

    total_duration = sum(seg_durations)

    # ── 2. 构建字幕时间轴 ──
    subtitles = []
    if segments:
        subtitles = _build_subtitle_data(segments, seg_durations)
    font = _load_font(SUBTITLE_FONT_SIZE) if subtitles else None

    # ── 3. 构建 slide → (图片, 音频列表, 时长) 的映射 ──
    # slide_segment_map: {slide_id: [seg_id_1, seg_id_2, ...]}
    # segments 的 id 从 1 开始，audio_paths 按 segment id 顺序排列（index = id - 1）
    if not slide_segment_map:
        # 如果没有提供映射，平均分配
        segs_per_slide = max(1, total_segs // len(slide_images))
        slide_segment_map = {}
        for idx, _ in enumerate(slide_images):
            start = idx * segs_per_slide
            end = start + segs_per_slide if idx < len(slide_images) - 1 else total_segs
            slide_segment_map[idx + 1] = list(range(start + 1, end + 1))

    # 按 slide 组织数据
    slides_data = []
    for slide_idx, img_path in enumerate(slide_images):
        slide_id = slide_idx + 1
        if not img_path or not Path(img_path).exists():
            print(f"幻灯片 {slide_id} 图片缺失，跳过")
            continue
        seg_ids = slide_segment_map.get(slide_id, [])
        # 收集这个 slide 的音频 clip 和时长
        slide_audio = []
        slide_dur = 0.0
        for seg_id in seg_ids:
            audio_idx = seg_id - 1  # segment id 从 1 开始
            if 0 <= audio_idx < len(audio_clips):
                slide_audio.append(audio_clips[audio_idx])
                slide_dur += seg_durations[audio_idx]
        slides_data.append({
            "image_path": img_path,
            "audio_clips": slide_audio,
            "duration": slide_dur,
            "slide_id": slide_id,
        })

    # ── 4. 为每张 slide 生成 Ken Burns clip ──
    transition = SLIDE_TRANSITION_DURATION
    prepared_images = []
    slide_clips = []
    current_time = 0.0

    # 计算交叉淡入淡出后的实际总时长
    valid_slides = [sd for sd in slides_data if sd["duration"] > 0
                    and sd.get("image_path") and Path(sd["image_path"]).exists()]
    n_valid = len(valid_slides)
    effective_total = sum(sd["duration"] for sd in valid_slides)
    if n_valid > 1 and transition > 0:
        effective_total -= transition * (n_valid - 1)

    for i, sd in enumerate(slides_data):
        if progress_callback:
            progress_callback(0.2 + i / len(slides_data) * 0.3,
                            f"生成幻灯片 {i+1}/{len(slides_data)}...")

        if sd["duration"] <= 0 or not sd.get("image_path") or not Path(sd["image_path"]).exists():
            continue

        prepared = _prepare_image(sd["image_path"])
        prepared_images.append(prepared)

        # 合并这个 slide 的所有音频为一个 clip
        if len(sd["audio_clips"]) == 1:
            combined_audio = sd["audio_clips"][0]
        else:
            combined_audio = CompositeAudioClip(sd["audio_clips"])

        img_clip = _ken_burns_clip(
            prepared, sd["duration"], reverse=(i % 2 == 1),
            total_duration=effective_total, start_time=current_time,
            subtitles=subtitles, font=font,
        ).set_audio(combined_audio)

        slide_clips.append(img_clip)
        # 考虑交叉淡入淡出：除第一张外，每张实际开始时间提前 transition 秒
        if len(slide_clips) == 1:
            current_time += sd["duration"]
        else:
            current_time += sd["duration"] - transition

    if not slide_clips:
        raise ValueError("没有可用的幻灯片片段")

    # ── 5. 交叉淡入淡出 + 拼接 ──
    if len(slide_clips) > 1 and transition > 0:
        if progress_callback:
            progress_callback(0.55, "添加转场效果...")
        # 第一个 clip 只加 fadeout
        slide_clips[0] = slide_clips[0].crossfadeout(transition)
        # 中间 clip 加 fadein + fadeout
        for j in range(1, len(slide_clips) - 1):
            slide_clips[j] = (slide_clips[j]
                            .crossfadein(transition)
                            .crossfadeout(transition))
        # 最后一个 clip 只加 fadein
        slide_clips[-1] = slide_clips[-1].crossfadein(transition)

        final_video = concatenate_videoclips(
            slide_clips, method="compose", padding=-transition
        )
    else:
        final_video = concatenate_videoclips(slide_clips, method="compose")

    # ── 6. 混合 BGM ──
    if bg_music_path and bg_music_path.exists():
        if progress_callback:
            progress_callback(0.6, "混合背景音乐...")
        try:
            bg_music = AudioFileClip(str(bg_music_path)).volumex(BG_MUSIC_VOLUME)
            if bg_music.duration < final_video.duration:
                bg_music = bg_music.fx(vfx.loop, duration=final_video.duration)
            else:
                bg_music = bg_music.subclip(0, final_video.duration)

            composite_audio = CompositeAudioClip([
                final_video.audio.volumex(NARRATION_VOLUME),
                bg_music,
            ])
            final_video = final_video.set_audio(composite_audio)
        except Exception as e:
            print(f"BGM 混合失败，使用纯旁白: {e}")

    if progress_callback:
        progress_callback(0.7, f"开始渲染（约 {final_video.duration:.0f} 秒视频）...")

    # ── 7. 渲染输出 ──
    render_logger = _StreamlitProgressLogger(progress_callback, 0.7, 1.0)

    final_video.write_videofile(
        str(output_path),
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="ultrafast",
        threads=4,
        logger=render_logger,
    )

    if progress_callback:
        progress_callback(1.0, "PPT 视频合成完成")

    # 清理临时文件
    for p in prepared_images:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass

    return output_path
