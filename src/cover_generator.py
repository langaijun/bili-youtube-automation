"""阶段2: 封面图生成"""
import base64
import os
import time
from http import HTTPStatus
from pathlib import Path

import dashscope
from dashscope import ImageSynthesis
from openai import OpenAI

from config import (
    DASHSCOPE_API_KEY, QWEN_MODEL, QWEN_BASE_URL, VL_MODEL,
    IMAGE_MODEL, IMAGE_SIZE,
)

dashscope.api_key = DASHSCOPE_API_KEY


def _get_llm_client() -> OpenAI:
    return OpenAI(api_key=DASHSCOPE_API_KEY, base_url=QWEN_BASE_URL)


def generate_cover_prompts(title: str, description: str) -> list[dict]:
    """用 Qwen 生成 2 个不同风格的封面提示词"""
    client = _get_llm_client()

    prompt = f"""请根据以下视频标题和描述，生成 2 个不同风格的 B站/YouTube 视频封面图提示词。

视频标题：{title}
视频描述：{description[:300]}

要求：
- 适合知识博主视频封面（高点击率）
- 不包含任何文字（文字会后期添加）
- 视觉冲击力强
- 输出 JSON 数组

格式：
[
  {{"style": "风格名称", "prompt": "详细英文提示词，高质量、16:9比例"}},
  {{"style": "风格名称", "prompt": "详细英文提示词"}}
]

只输出 JSON，不要其他文字。"""

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": "你是一个封面设计提示词专家，输出严格 JSON。"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    import json
    result = json.loads(response.choices[0].message.content.strip())
    # 处理可能的外层 key
    if isinstance(result, dict):
        for key in result:
            if isinstance(result[key], list):
                return result[key]
    return result


def generate_covers(prompts: list[dict], output_dir: Path) -> list[Path]:
    """调用万相生成封面图"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for i, prompt_info in enumerate(prompts):
        prompt_text = prompt_info.get("prompt", prompt_info) if isinstance(prompt_info, dict) else str(prompt_info)

        try:
            response = ImageSynthesis.async_call(
                model=IMAGE_MODEL,
                prompt=prompt_text,
                n=1,
                size=IMAGE_SIZE,
            )

            if response.status_code == HTTPStatus.OK:
                result = ImageSynthesis.wait(response.output.task_id)
                if result.status_code == HTTPStatus.OK and result.output.results:
                    image_url = result.output.results[0].get("url", "")
                    if image_url:
                        import requests
                        img_data = requests.get(image_url, timeout=30).content
                        img_path = output_dir / f"cover_{i+1:02d}.jpg"
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                        paths.append(img_path)
            time.sleep(1)  # 避免限流
        except Exception as e:
            print(f"❌ 封面 {i+1} 生成失败: {e}")

    return paths


def enhance_prompt_with_reference(base_prompt: str, reference_image_path: Path) -> str:
    """用 Qwen-VL 分析参考图，增强 prompt 使其风格一致。

    Args:
        base_prompt: 原始图片生成 prompt
        reference_image_path: 参考图路径

    Returns:
        增强后的 prompt
    """
    reference_image_path = Path(reference_image_path)
    if not reference_image_path.exists():
        return base_prompt

    try:
        with open(reference_image_path, "rb") as f:
            img_bytes = f.read()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        suffix = reference_image_path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(suffix, "image/jpeg")

        client = _get_llm_client()
        response = client.chat.completions.create(
            model=VL_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Analyze this reference image's visual style, color palette, "
                                "composition, and mood. Then enhance the following image generation "
                                "prompt to match this reference's style. Return ONLY the enhanced "
                                "English prompt, nothing else.\n\n"
                                f"Original prompt: {base_prompt}"
                            ),
                        },
                    ],
                }
            ],
            temperature=0.7,
        )
        enhanced = response.choices[0].message.content.strip()
        return enhanced if enhanced else base_prompt
    except Exception as e:
        print(f"参考图增强 prompt 失败: {e}")
        return base_prompt
