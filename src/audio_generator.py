"""阶段3b: CosyVoice TTS 旁白音频生成"""
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat

from config import DASHSCOPE_API_KEY, TTS_MODEL, TTS_CLONE_MODEL, TTS_VOICE

dashscope.api_key = DASHSCOPE_API_KEY

# 语音注册服务（特性守卫）
try:
    from dashscope.audio.tts_v2 import VoiceEnrollmentService
    _HAS_ENROLLMENT = True
except ImportError:
    _HAS_ENROLLMENT = False


def _make_synthesizer(voice: str = None, is_cloned: bool = False) -> SpeechSynthesizer:
    """创建 TTS 合成器。内置音色用 v1，克隆音色用 v3-flash。"""
    model = TTS_CLONE_MODEL if is_cloned else TTS_MODEL
    return SpeechSynthesizer(
        model=model,
        voice=voice or TTS_VOICE,
        format=AudioFormat.MP3_22050HZ_MONO_256KBPS,
    )


def enroll_custom_voice(audio_path: Path, voice_name: str = "custom") -> str | None:
    """注册自定义音色。

    先将本地音频上传到 DashScope 获取 URL，再调用 VoiceEnrollmentService 注册。

    Args:
        audio_path: 参考音频路径（10-20秒清晰语音）
        voice_name: 自定义名称前缀

    Returns:
        voice_id 字符串，失败返回 None
    """
    if not _HAS_ENROLLMENT:
        print("VoiceEnrollmentService 不可用，请升级 dashscope SDK")
        return None

    audio_path = Path(audio_path)

    # 上传音频到 DashScope 获取可访问的 URL
    audio_url = _upload_audio_for_clone(audio_path)
    if not audio_url:
        return None

    try:
        service = VoiceEnrollmentService()
        voice_id = service.create_voice(
            target_model=TTS_CLONE_MODEL,
            prefix=voice_name,
            url=audio_url,
        )
        return voice_id
    except Exception as e:
        print(f"语音注册失败: {e}")
        return None


def _upload_audio_for_clone(audio_path: Path) -> str | None:
    """通过 DashScope Files API 上传音频，获取签名 URL。

    Returns:
        可访问的音频 URL，失败返回 None
    """
    from dashscope import Files

    try:
        # 上传（purpose="inference" 绕过 JSONL 格式校验）
        upload_resp = Files.upload(file_path=str(audio_path), purpose="inference")
        if upload_resp.status_code != 200:
            print(f"上传失败: {upload_resp.message}")
            return None

        uploaded = upload_resp.output.get("uploaded_files", [])
        if not uploaded:
            print("上传失败: 无 uploaded_files")
            return None

        file_id = uploaded[0]["file_id"]

        # 获取文件 URL
        get_resp = Files.get(file_id)
        if get_resp.status_code != 200:
            print(f"获取文件信息失败: {get_resp.message}")
            return None

        url = get_resp.output.get("url")
        if not url:
            print("获取文件信息失败: 无 url")
            return None

        return url
    except Exception as e:
        print(f"音频上传失败: {e}")
        return None


def preview_voice(voice: str, text: str = "你好，欢迎收看本期视频，今天我们来聊一个有趣的话题。",
                  is_cloned: bool = False) -> bytes | None:
    """
    生成音色试听样本。

    Args:
        voice: 音色名称或 voice_id
        text: 试听文本
        is_cloned: 是否为克隆音色

    Returns:
        MP3 音频字节数据，失败返回 None
    """
    try:
        synthesizer = _make_synthesizer(voice, is_cloned=is_cloned)
        audio_data = synthesizer.call(text)
        return audio_data if audio_data else None
    except Exception as e:
        print(f"音色试听生成失败: {e}")
        return None


def generate_single_audio(segment: dict, output_dir: Path,
                          voice: str = None, is_cloned: bool = False) -> Path | None:
    """
    生成单段旁白音频。

    Args:
        segment: 段落 dict，含 id 和 narration_text
        output_dir: 输出目录
        voice: 音色名称或 voice_id
        is_cloned: 是否为克隆音色

    Returns:
        生成的音频路径，失败返回 None
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    text = segment.get("narration_text", "")
    if not text.strip():
        return None

    audio_path = output_dir / f"{segment['id']:02d}.mp3"
    try:
        synthesizer = _make_synthesizer(voice, is_cloned=is_cloned)
        audio_data = synthesizer.call(text)
        if audio_data:
            with open(audio_path, "wb") as f:
                f.write(audio_data)
            return audio_path
    except Exception as e:
        print(f"段落 {segment['id']} 音频生成失败: {e}")
    return None


def generate_audio(segments: list[dict], output_dir: Path,
                   voice: str = None, is_cloned: bool = False,
                   progress_callback=None) -> list[Path]:
    """
    批量生成旁白音频。

    Args:
        segments: 脚本段落列表，每个含 id 和 narration_text
        output_dir: 音频输出目录
        voice: 音色名称或 voice_id
        is_cloned: 是否为克隆音色
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
            synthesizer = _make_synthesizer(voice, is_cloned=is_cloned)
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
