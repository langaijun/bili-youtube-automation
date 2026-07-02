"""阶段3a: 配图生成（2张选1张）"""
import time
from http import HTTPStatus
from pathlib import Path

import dashscope
import requests
from dashscope import ImageSynthesis
from openai import OpenAI

from config import (
    DASHSCOPE_API_KEY, QWEN_MODEL, QWEN_BASE_URL,
    IMAGE_MODEL, IMAGE_SIZE, IMAGE_STYLES,
)

dashscope.api_key = DASHSCOPE_API_KEY


def _get_llm_client() -> OpenAI:
    return OpenAI(api_key=DASHSCOPE_API_KEY, base_url=QWEN_BASE_URL)


def generate_scene_prompts(title: str, description: str, image_style: str) -> list[str]:
    """用 Qwen 为 2 张配图生成提示词"""
    client = _get_llm_client()
    style_prefix = IMAGE_STYLES.get(image_style, IMAGE_STYLES["极简插画"])

    prompt = f"""根据以下视频标题和描述，生成 2 张场景配图的英文提示词。

视频标题：{title}
视频描述：{description[:300]}
图片风格：{style_prefix}

要求：
- 两张图应该有不同的视角/场景，但风格统一
- 适合知识博主深度解读视频的背景配图
- 不包含任何文字或人物面部特写
- 每张提示词都要包含风格前缀: {style_prefix}

输出 JSON：
{{
  "prompts": [
    "英文提示词1",
    "英文提示词2"
  ]
}}"""

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": "你是一个图像生成提示词专家，输出严格 JSON。"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    import json
    result = json.loads(response.choices[0].message.content.strip())
    return result.get("prompts", list(result.values())[0] if result else [])


def generate_images(prompts: list[str], output_dir: Path,
                    progress_callback=None) -> list[Path]:
    """调用万相生成配图"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for i, prompt_text in enumerate(prompts):
        if progress_callback:
            progress_callback(i / len(prompts), f"生成配图 {i+1}/{len(prompts)}...")

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
                        img_data = requests.get(image_url, timeout=30).content
                        img_path = output_dir / f"scene_{i+1:02d}.jpg"
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                        paths.append(img_path)
            time.sleep(1)
        except Exception as e:
            print(f"❌ 配图 {i+1} 生成失败: {e}")

    if progress_callback:
        progress_callback(1.0, "配图生成完成")

    return paths
