"""阶段3c: 字幕 .srt 生成"""
from pathlib import Path
from pydub import AudioSegment


def _format_srt_time(seconds: float) -> str:
    """将秒数格式化为 SRT 时间格式: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_subtitles(segments: list[dict], audio_paths: list[Path],
                       output_path: Path) -> Path:
    """
    根据旁白文本和音频时长生成 .srt 字幕文件。

    Args:
        segments: 脚本段落列表 (含 id, narration_text)
        audio_paths: 对应的音频文件路径列表（顺序与 segments 一致）
        output_path: .srt 文件输出路径

    Returns:
        生成的 .srt 文件路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    srt_entries = []
    current_time = 0.0

    for i, (segment, audio_path) in enumerate(zip(segments, audio_paths)):
        text = segment.get("narration_text", "").strip()
        if not text or not audio_path.exists():
            continue

        # 获取音频实际时长
        try:
            audio = AudioSegment.from_mp3(str(audio_path))
            duration = len(audio) / 1000.0  # 毫秒转秒
        except Exception:
            duration = segment.get("estimated_duration", 45)

        start_time = current_time
        end_time = current_time + duration

        srt_entries.append(
            f"{i + 1}\n"
            f"{_format_srt_time(start_time)} --> {_format_srt_time(end_time)}\n"
            f"{text}\n"
        )

        current_time = end_time + 0.5  # 段落间 0.5s 间隔

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_entries))

    return output_path
