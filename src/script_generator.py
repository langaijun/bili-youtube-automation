"""阶段1: Qwen LLM 脚本生成"""
import json
from openai import OpenAI
from config import (
    QWEN_MODEL, QWEN_BASE_URL, DASHSCOPE_API_KEY, IMAGE_STYLES,
    PPT_SLIDE_COUNT_MIN, PPT_SLIDE_COUNT_MAX,
)


def _get_client() -> OpenAI:
    return OpenAI(api_key=DASHSCOPE_API_KEY, base_url=QWEN_BASE_URL)


def _build_classic_prompt(user_input: str, image_style: str, style_prompt: str) -> str:
    """构建经典模式（单图Ken Burns）的 prompt"""
    return f"""你是一个擅长B站/YouTube知识博主视频的脚本专家。

用户会给你一段原始内容（可能是书籍观点、文章片段、想法等），请你：
1. 优化成适合"静态图片 + 旁白"风格的深度解读视频脚本
2. 拆分成 15-18 个段落（每段 40-90 秒，总时长 12 分钟以上）
3. 规划 2 张场景配图（标注每张覆盖哪些段落）
4. 输出严格的 JSON，不要任何额外文字

重要约束：
- 所有内容必须是你的原创分析和类比，不得照搬原文段落
- 在 source_attribution 中标注原作者和出处
- 使用口语化中文表达，适合语音朗读
- 要有强钩子开头、层层递进、情感升华和 CTA（关注/点赞/收藏）
- image_prompt 用英文，匹配以下风格: {style_prompt}

JSON 结构：
{{
  "title": "吸引人的视频标题（适合B站和YouTube）",
  "description": "视频描述（包含关键词、出处标注，300-500字）",
  "source_attribution": "本视频基于 xxx 的 xxx 个人解读",
  "image_style": "{image_style}",
  "video_type": "classic",
  "scenes": [
    {{
      "id": 1,
      "image_prompt": "英文提示词，匹配风格: {style_prompt}",
      "note": "场景描述"
    }},
    {{
      "id": 2,
      "image_prompt": "英文提示词",
      "note": "场景描述"
    }}
  ],
  "segments": [
    {{
      "id": 1,
      "narration_text": "第一段旁白（口语化、原创分析）",
      "scene_id": 1,
      "estimated_duration": 45
    }}
  ]
}}

用户输入内容：
{user_input}"""


def _build_ppt_prompt(user_input: str, image_style: str, style_prompt: str) -> str:
    """构建PPT模式（多幻灯片）的 prompt"""
    return f"""你是一个擅长B站/YouTube知识博主视频的脚本专家。

用户会给你一段原始内容（可能是书籍观点、文章片段、想法等），请你：
1. 优化成适合"多张幻灯片配图 + 旁白"风格的深度解读视频脚本
2. 拆分成 15-18 个段落（每段 40-90 秒，总时长 12 分钟以上）
3. 规划 {PPT_SLIDE_COUNT_MIN}-{PPT_SLIDE_COUNT_MAX} 张幻灯片配图，每张对应1-3个段落
4. 输出严格的 JSON，不要任何额外文字

重要约束：
- 所有内容必须是你的原创分析和类比，不得照搬原文段落
- 在 source_attribution 中标注原作者和出处
- 使用口语化中文表达，适合语音朗读
- 要有强钩子开头、层层递进、情感升华和 CTA（关注/点赞/收藏）
- image_prompt 用英文，匹配以下风格: {style_prompt}
- 每张幻灯片的 image_prompt 应该描述不同的场景/画面，视觉上有明显区分
- segment_ids 必须覆盖所有段落，每个段落只能分配给一张幻灯片

JSON 结构：
{{
  "title": "吸引人的视频标题（适合B站和YouTube）",
  "description": "视频描述（包含关键词、出处标注，300-500字）",
  "source_attribution": "本视频基于 xxx 的 xxx 个人解读",
  "image_style": "{image_style}",
  "video_type": "ppt",
  "slides": [
    {{
      "id": 1,
      "image_prompt": "英文提示词，描述第1张幻灯片的画面",
      "note": "场景描述（中文）",
      "segment_ids": [1, 2]
    }},
    {{
      "id": 2,
      "image_prompt": "英文提示词，描述第2张幻灯片的画面（与第1张视觉上有明显不同）",
      "note": "场景描述",
      "segment_ids": [3, 4, 5]
    }}
  ],
  "segments": [
    {{
      "id": 1,
      "narration_text": "第一段旁白（口语化、原创分析）",
      "slide_id": 1,
      "estimated_duration": 45
    }}
  ]
}}

用户输入内容：
{user_input}"""


def generate_script(user_input: str, image_style: str, output_dir=None,
                    video_type: str = "classic") -> dict:
    """
    调用 Qwen 生成结构化视频脚本。

    Args:
        user_input: 用户原始文字（想法/关键词/文章片段）
        image_style: 图片风格名称（对应 IMAGE_STYLES 的 key）
        output_dir: 输出目录（可选，用于保存 script.json）
        video_type: "ppt"（多幻灯片）或 "classic"（单图Ken Burns）

    Returns:
        结构化脚本 dict
    """
    client = _get_client()
    style_cfg = IMAGE_STYLES.get(image_style, IMAGE_STYLES["极简插画"])
    style_prompt = style_cfg["prompt_prefix"]

    if video_type == "ppt":
        prompt = _build_ppt_prompt(user_input, image_style, style_prompt)
    else:
        prompt = _build_classic_prompt(user_input, image_style, style_prompt)

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": "你是一个专业的视频脚本编剧，输出严格 JSON。"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    content = response.choices[0].message.content.strip()
    script = json.loads(content)

    if output_dir:
        from pathlib import Path
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        script_path = output_path / "script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)

    return script


def regenerate_segment(segment_text: str, image_style: str) -> str:
    """
    重新生成单个段落的旁白文本。

    Args:
        segment_text: 原始段落文本（用于理解上下文）
        image_style: 图片风格

    Returns:
        新的旁白文本
    """
    client = _get_client()
    style_cfg = IMAGE_STYLES.get(image_style, IMAGE_STYLES["极简插画"])
    style_prompt = style_cfg["prompt_prefix"]

    prompt = f"""请重新优化以下视频旁白段落，要求：
- 口语化中文，适合语音朗读
- 原创分析，不照搬原文
- 保持与整体视频风格一致
- 长度适合 40-90 秒朗读

原始文本：
{segment_text}

请直接输出优化后的文本，不要任何额外标记。"""

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": "你是一个专业的视频旁白写手。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()
