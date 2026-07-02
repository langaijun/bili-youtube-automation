"""阶段4: MoviePy 视频合成（配图 + Ken Burns + 旁白 + BGM）"""
from pathlib import Path

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    ImageClip,
    concatenate_videoclips,
    vfx,
)
from PIL import Image

from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    BG_MUSIC_VOLUME, NARRATION_VOLUME, FADE_DURATION,
    KB_ZOOM_START, KB_ZOOM_END,
)


def _prepare_image(image_path: Path) -> str:
    """将配图 resize 到视频尺寸"""
    img = Image.open(str(image_path))
    img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)
    prepared_path = image_path.with_stem(image_path.stem + "_prepared")
    img.save(str(prepared_path))
    return str(prepared_path)


def compose_video(
    image_path: Path,
    audio_paths: list[Path],
    output_path: Path,
    bg_music_path: Path = None,
    progress_callback=None,
) -> Path:
    """
    合成视频: 1张配图 + Ken Burns 动效 + 多段旁白 + 可选BGM

    Args:
        image_path: 选定的配图路径
        audio_paths: 旁白音频路径列表
        output_path: 输出视频路径
        bg_music_path: 背景音乐路径（可选）
        progress_callback: 进度回调

    Returns:
        生成的视频路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prepared_image = _prepare_image(image_path)

    clips = []
    total = len(audio_paths)

    for i, audio_path in enumerate(audio_paths):
        if progress_callback:
            progress_callback(
                i / total * 0.8,
                f"处理片段 {i+1}/{total}..."
            )

        audio_clip = AudioFileClip(str(audio_path))
        duration = audio_clip.duration + 0.5  # padding

        # Ken Burns 效果: 奇数段放大，偶数段缩小
        if i % 2 == 0:
            zoom_start, zoom_end = KB_ZOOM_START, KB_ZOOM_END
        else:
            zoom_start, zoom_end = KB_ZOOM_END, KB_ZOOM_START

        def make_resize_func(zs, ze, dur):
            def resize_func(t):
                progress = t / dur if dur > 0 else 0
                return zs + (ze - zs) * progress
            return resize_func

        img_clip = (
            ImageClip(prepared_image)
            .set_duration(duration)
            .set_audio(audio_clip)
            .resize(make_resize_func(zoom_start, zoom_end, duration))
            .fadein(FADE_DURATION)
            .fadeout(FADE_DURATION)
        )
        clips.append(img_clip)

    if progress_callback:
        progress_callback(0.8, "拼接片段...")

    final_video = concatenate_videoclips(clips, method="compose")

    # 混合 BGM
    if bg_music_path and bg_music_path.exists():
        if progress_callback:
            progress_callback(0.85, "混合背景音乐...")

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

    if progress_callback:
        progress_callback(0.9, "渲染视频...")

    final_video.write_videofile(
        str(output_path),
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="medium",
        threads=4,
    )

    if progress_callback:
        progress_callback(1.0, "视频合成完成")

    # 清理临时文件
    try:
        Path(prepared_image).unlink(missing_ok=True)
    except Exception:
        pass

    return output_path
