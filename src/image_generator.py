"""阶段3a: 配图生成（2张选1张）"""
import json
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


def _get_style_config(image_style: str) -> dict:
    """获取风格配置"""
    return IMAGE_STYLES.get(image_style, IMAGE_STYLES["极简插画"])


def generate_scene_prompts(title: str, description: str, image_style: str) -> list[str]:
    """用 Qwen 为 2 张配图生成提示词"""
    client = _get_llm_client()
    style_cfg = _get_style_config(image_style)
    prefix = style_cfg["prompt_prefix"]

    prompt = f"""根据以下视频标题和描述，生成 2 张场景配图的英文提示词。

视频标题：{title}
视频描述：{description[:300]}
图片风格要求：{prefix}

要求：
- 两张图应该有不同的视角/场景，但风格统一
- 适合知识博主深度解读视频的背景配图
- 不包含任何文字或人物面部特写
- 每张提示词描述具体的画面内容（场景、物体、氛围），不要重复风格描述

输出 JSON：
{{
  "prompts": [
    "英文提示词1（描述画面内容）",
    "英文提示词2（描述画面内容）"
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

    result = json.loads(response.choices[0].message.content.strip())
    raw_prompts = result.get("prompts", list(result.values())[0] if result else [])

    # 强制拼接风格前缀到每个 prompt
    final_prompts = [f"{prefix}, {p}" for p in raw_prompts]
    return final_prompts


def generate_images(prompts: list[str], output_dir: Path,
                    image_style: str = "极简插画",
                    progress_callback=None) -> list[Path]:
    """
    调用万相生成配图，使用 style 参数 + prompt 前缀双重控制风格。

    Args:
        prompts: 已包含风格前缀的提示词列表
        output_dir: 输出目录
        image_style: 图片风格名称（用于获取 API style 参数）
        progress_callback: 进度回调
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    style_cfg = _get_style_config(image_style)
    api_style = style_cfg.get("style", "<auto>")

    for i, prompt_text in enumerate(prompts):
        if progress_callback:
            progress_callback(i / len(prompts), f"生成配图 {i+1}/{len(prompts)}...")

        try:
            call_kwargs = dict(
                model=IMAGE_MODEL,
                prompt=prompt_text,
                n=1,
                size=IMAGE_SIZE,
            )
            # wanx-v1 支持 style 参数
            if IMAGE_MODEL == "wanx-v1":
                call_kwargs["style"] = api_style

            response = ImageSynthesis.async_call(**call_kwargs)

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
            print(f"配图 {i+1} 生成失败: {e}")

    if progress_callback:
        progress_callback(1.0, "配图生成完成")

    return paths


def generate_slide_images(slides: list[dict], output_dir: Path,
                          image_style: str = "极简插画",
                          progress_callback=None) -> list[Path]:
    """
    为每个 slide 生成一张图片（PPT 模式专用）。

    Args:
        slides: 脚本中的 slides 列表，每个含 id, image_prompt
        output_dir: 输出目录
        image_style: 图片风格名称（用于获取 API style 参数）
        progress_callback: 进度回调

    Returns:
        生成的图片路径列表（顺序与 slides 一致）
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    style_cfg = _get_style_config(image_style)
    api_style = style_cfg.get("style", "<auto>")
    prefix = style_cfg["prompt_prefix"]
    total = len(slides)

    for i, slide in enumerate(slides):
        if progress_callback and total > 0:
            progress_callback(i / total, f"生成幻灯片 {i+1}/{total}...")

        raw_prompt = slide.get("image_prompt", "")
        prompt_text = f"{prefix}, {raw_prompt}"
        generated = False

        try:
            call_kwargs = dict(
                model=IMAGE_MODEL,
                prompt=prompt_text,
                n=1,
                size=IMAGE_SIZE,
            )
            if IMAGE_MODEL == "wanx-v1":
                call_kwargs["style"] = api_style

            response = ImageSynthesis.async_call(**call_kwargs)

            if response.status_code == HTTPStatus.OK:
                result = ImageSynthesis.wait(response.output.task_id)
                if result.status_code == HTTPStatus.OK and result.output.results:
                    image_url = result.output.results[0].get("url", "")
                    if image_url:
                        img_data = requests.get(image_url, timeout=30).content
                        img_path = output_dir / f"slide_{slide['id']:02d}.jpg"
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                        paths.append(img_path)
                        generated = True
            time.sleep(1)
        except Exception as e:
            print(f"幻灯片 {slide['id']} 图片生成失败: {e}")

        # 失败时追加 None，保持与 slides 列表的 1:1 索引对应
        if not generated:
            paths.append(None)

    ok_count = sum(1 for p in paths if p is not None)
    if progress_callback:
        progress_callback(1.0, f"幻灯片图片生成完成 ({ok_count}/{total})")

    return paths
