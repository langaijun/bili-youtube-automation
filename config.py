"""全局配置 + 风格预设"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# DashScope API Key
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# LLM
QWEN_MODEL = "qwen-max"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# TTS
TTS_MODEL = "cosyvoice-v1"
TTS_VOICE = "longyue"  # 默认音色

# 可选音色列表
TTS_VOICES = {
    "龙悦 (女声-讲故事)": "longyue",
    "龙小淳 (女声-温暖)": "longxiaochun",
    "龙小夏 (女声-温柔)": "longxiaoxia",
    "龙婉 (女声-标准)": "longwan",
    "龙静 (女声)": "longjing",
    "龙小白 (女声)": "longxiaobai",
    "龙书 (男声-叙事)": "longshu",
    "龙城 (男声)": "longcheng",
    "龙华 (男声)": "longhua",
    "龙飞 (男声)": "longfei",
    "龙硕 (男声)": "longshuo",
    "龙老铁 (男声-随性)": "longlaotie",
}

# 图片风格预设（万相照相馆风格）
# style: 万相 API style 参数 (wanx-v1 支持)
# prompt_prefix: 追加到 prompt 前的风格描述词
IMAGE_STYLES = {
    "极简插画": {
        "style": "<anime>",
        "prompt_prefix": "minimalist flat illustration, vector art style, clean geometric shapes, soft pastel color palette, no texture, simple background, modern graphic design",
    },
    "电影感叙事": {
        "style": "<photography>",
        "prompt_prefix": "cinematic still frame, anamorphic lens, dramatic chiaroscuro lighting, 35mm film grain, shallow depth of field, movie scene composition, color graded",
    },
    "涂鸦风": {
        "style": "<sketch>",
        "prompt_prefix": "street art, graffiti style, bold spray paint colors, urban vibe, expressive brush strokes, pop art influence",
    },
    "灵魂画手": {
        "style": "<sketch>",
        "prompt_prefix": "expressive hand-drawn sketch, artistic charcoal strokes, emotional and dynamic, raw creative energy, black and white with selective color",
    },
    "杂志封面": {
        "style": "<photography>",
        "prompt_prefix": "magazine cover style, editorial photography, high contrast, studio lighting, professional composition, sharp focus",
    },
    "水彩画": {
        "style": "<watercolor>",
        "prompt_prefix": "delicate watercolor painting, soft color bleeding, visible paper texture, translucent washes, artistic brushwork",
    },
    "油画": {
        "style": "<oil painting>",
        "prompt_prefix": "classical oil painting, rich impasto texture, deep colors, masterful brushwork, gallery quality",
    },
    "中国画": {
        "style": "<chinese painting>",
        "prompt_prefix": "traditional Chinese ink painting, xuan paper, elegant brushwork, negative space, zen composition",
    },
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
