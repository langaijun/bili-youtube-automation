"""阶段3b: CosyVoice TTS 旁白音频生成"""
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat

from config import DASHSCOPE_API_KEY, TTS_MODEL, TTS_VOICE

dashscope.api_key = DASHSCOPE_API_KEY


def _make_synthesizer(voice: str = None) -> SpeechSynthesizer:
    """创建 TTS 合成器"""
    return SpeechSynthesizer(
        model=TTS_MODEL,
        voice=voice or TTS_VOICE,
        format=AudioFormat.MP3_22050HZ_MONO_256KBPS,
    )


def generate_audio(segments: list[dict], output_dir: Path,
                   voice: str = None,
                   progress_callback=None) -> list[Path]:
    """
    批量生成旁白音频。

    Args:
        segments: 脚本段落列表，每个含 id 和 narration_text
        output_dir: 音频输出目录
        voice: 音色名称（如 "longyue"），默认用配置
        progress_callback: 进度回调 (progress: float, message: str)

    Returns:
        生成的音频文件路径列表
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    total = len(segments)

    for i, segment in enumerate(segments):
        if progress_callback:
            progress_callback(
                i / total,
                f"生成旁白 {i+1}/{total}: {segment.get('narration_text', '')[:20]}..."
            )

        text = segment.get("narration_text", "")
        if not text.strip():
            continue

        audio_path = output_dir / f"{segment['id']:02d}.mp3"
        try:
            synthesizer = _make_synthesizer(voice)
            audio_data = synthesizer.call(text)

            if audio_data:
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
                paths.append(audio_path)
            else:
                print(f"段落 {segment['id']} TTS 返回空数据")
        except Exception as e:
            print(f"段落 {segment['id']} 音频生成失败: {e}")

    if progress_callback:
        progress_callback(1.0, f"旁白生成完成 ({len(paths)}/{total})")

    return paths


def regenerate_single_audio(text: str, audio_path: Path, voice: str = None) -> bool:
    """
    重新生成单段音频（局部重做）。

    Args:
        text: 新的旁白文本
        audio_path: 输出路径
        voice: 音色名称

    Returns:
        是否成功
    """
    try:
        synthesizer = _make_synthesizer(voice)
        audio_data = synthesizer.call(text)

        if audio_data:
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            with open(audio_path, "wb") as f:
                f.write(audio_data)
            return True
    except Exception as e:
        print(f"单段音频重做失败: {e}")
    return False
