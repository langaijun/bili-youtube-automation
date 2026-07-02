"""全局配置 + 风格预设"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# DashScope API Key
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# LLM
QWEN_MODEL = "qwen-max"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# TTS
TTS_MODEL = "cosyvoice-v1"
TTS_VOICE = "longyue"
TTS_FORMAT = "mp3"
TTS_SAMPLE_RATE = 22050

# 图片风格预设（万相照相馆风格）
IMAGE_STYLES = {
    "极简插画": "minimalist illustration, flat design, clean lines, soft colors",
    "电影感叙事": "cinematic photography, dramatic lighting, film grain, 35mm lens",
    "涂鸦风": "street art, graffiti style, bold colors, urban vibe",
    "灵魂画手": "expressive sketch, hand-drawn, artistic, emotional strokes",
    "杂志封面": "magazine cover style, editorial photography, high contrast",
}
DEFAULT_STYLE = "极简插画"

# 图片生成
IMAGE_MODEL = "wanx2.1-t2i-plus"
IMAGE_SIZE = "1280*720"

# 视频
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 24
BG_MUSIC_VOLUME = 0.05
NARRATION_VOLUME = 1.2
FADE_DURATION = 0.5

# Ken Burns
KB_ZOOM_START = 1.0
KB_ZOOM_END = 1.05

# 路径
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
FONT_PATH = ASSETS_DIR / "fonts" / "chinese_font.ttf"
MUSIC_DIR = ASSETS_DIR / "music"
OUTPUT_DIR = BASE_DIR / "output"
