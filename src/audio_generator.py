"""阶段3b: CosyVoice TTS 旁白音频生成"""
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

from config import DASHSCOPE_API_KEY, TTS_MODEL, TTS_VOICE, TTS_FORMAT, TTS_SAMPLE_RATE

dashscope.api_key = DASHSCOPE_API_KEY


def generate_audio(segments: list[dict], output_dir: Path,
                   progress_callback=None) -> list[Path]:
    """
    批量生成旁白音频。

    Args:
        segments: 脚本段落列表，每个含 id 和 narration_text
        output_dir: 音频输出目录
        progress_callback: 进度回调 (progress: float, message: str)

    Returns:
        生成的音频文件路径列表
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for i, segment in enumerate(segments):
        if progress_callback:
            progress_callback(
                i / len(segments),
                f"生成旁白 {i+1}/{len(segments)}..."
            )

        text = segment.get("narration_text", "")
        if not text.strip():
            continue

        audio_path = output_dir / f"{segment['id']:02d}.mp3"
        try:
            synthesizer = SpeechSynthesizer(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                format=TTS_FORMAT,
                sample_rate=TTS_SAMPLE_RATE,
            )
            audio_data = synthesizer.call(text)

            if audio_data:
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
                paths.append(audio_path)
            else:
                print(f"❌ 段落 {segment['id']} TTS 返回空数据")
        except Exception as e:
            print(f"❌ 段落 {segment['id']} 音频生成失败: {e}")

    if progress_callback:
        progress_callback(1.0, "旁白生成完成")

    return paths


def regenerate_single_audio(text: str, audio_path: Path) -> bool:
    """
    重新生成单段音频（局部重做）。

    Args:
        text: 新的旁白文本
        audio_path: 输出路径

    Returns:
        是否成功
    """
    try:
        synthesizer = SpeechSynthesizer(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            format=TTS_FORMAT,
            sample_rate=TTS_SAMPLE_RATE,
        )
        audio_data = synthesizer.call(text)

        if audio_data:
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            with open(audio_path, "wb") as f:
                f.write(audio_data)
            return True
    except Exception as e:
        print(f"❌ 单段音频重做失败: {e}")
    return False
