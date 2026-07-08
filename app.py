"""半自动视频制作 Agent - Streamlit 主界面"""
import json
import sys
from pathlib import Path

import streamlit as st

# 确保 src 目录可导入
sys.path.insert(0, str(Path(__file__).parent))

from config import IMAGE_STYLES, DEFAULT_STYLE, OUTPUT_DIR, MUSIC_DIR, TTS_VOICES, TTS_VOICE, PPT_SLIDE_COUNT_MIN, PPT_SLIDE_COUNT_MAX

st.set_page_config(page_title="半自动视频制作 Agent", page_icon="🎬", layout="wide")
st.title("🎬 半自动视频制作 Agent")
st.caption("输入内容 → AI 生成脚本 → 配图+旁白 → 合成视频 | 适用于 B站/YouTube 深度解读")

# ── Session State 初始化 ──
defaults = {
    "project_name": "",
    "video_type": "ppt",           # "ppt" 或 "classic"
    "image_style": DEFAULT_STYLE,
    "script": None,
    "script_confirmed": False,
    "covers": [],
    "cover_prompts": [],
    "selected_cover": None,
    "scene_images": [],
    "scene_prompts": [],
    "selected_scene": None,
    "slide_images": [],            # PPT 模式幻灯片图片
    "slide_prompts": [],           # PPT 模式幻灯片提示词
    "audio_paths": {},
    "selected_voice": TTS_VOICE,
    "voice_preview_bytes": None,
    "cloned_voice_id": None,
    "cloned_voice_name": None,
    "_ref_cover_path": None,
    "_ref_scene_path": None,
    "bgm_path": None,
    "video_path": None,
    "subtitle_path": None,
    "active_tab": 0,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# 迁移守卫: audio_paths 从 list 改为 dict
if isinstance(st.session_state.audio_paths, list):
    old = st.session_state.audio_paths
    st.session_state.audio_paths = {}
    if st.session_state.script:
        for i, p in enumerate(old):
            segs = st.session_state.script.get("segments", [])
            if i < len(segs):
                st.session_state.audio_paths[segs[i]["id"]] = p


def get_output_dir() -> Path:
    name = st.session_state.project_name or "untitled"
    d = OUTPUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def switch_tab(tab_index: int, message: str = ""):
    """提示用户切换到指定 Tab（Streamlit 不支持程序化切换）"""
    st.session_state.active_tab = tab_index
    if message:
        st.toast(message, icon="➡️")


# ── Tab 布局 ──
tab_labels = ["① 脚本", "② 封面", "③ 素材", "④ 合成", "⑤ 输出"]
tabs = st.tabs(tab_labels)

# ════════════════════════════════════════════
# Tab ① 脚本生成
# ════════════════════════════════════════════
with tabs[0]:
    st.header("脚本生成")

    col1, col2, col3 = st.columns(3)
    with col1:
        project_name = st.text_input(
            "项目名称",
            value=st.session_state.project_name,
            placeholder="例如: naval_财富自由解读",
        )
        st.session_state.project_name = project_name

    with col2:
        video_type_labels = ["PPT模式（多幻灯片）", "经典模式（单图）"]
        video_type_values = ["ppt", "classic"]
        current_vt_idx = 0
        if st.session_state.video_type in video_type_values:
            current_vt_idx = video_type_values.index(st.session_state.video_type)
        selected_vt_label = st.selectbox(
            "视频类型",
            video_type_labels,
            index=current_vt_idx,
            help="PPT模式: 8-12张不同配图轮播; 经典模式: 单张配图+Ken Burns",
        )
        st.session_state.video_type = video_type_values[video_type_labels.index(selected_vt_label)]

    with col3:
        image_style = st.selectbox(
            "图片风格",
            options=list(IMAGE_STYLES.keys()),
            index=list(IMAGE_STYLES.keys()).index(st.session_state.image_style),
        )
        st.session_state.image_style = image_style

    user_input = st.text_area(
        "输入你的内容（想法/关键词/文章片段/书名）",
        height=200,
        placeholder="例如：我最近在读 Naval Ravikant 的《The Almanack of Naval Ravikant》，他关于财富自由的观点...",
    )

    if st.button("🤖 生成脚本", type="primary", disabled=not user_input.strip()):
        with st.spinner("正在生成脚本，请稍候（约30秒）..."):
            from src.script_generator import generate_script
            output_dir = get_output_dir()
            script = generate_script(user_input, image_style, output_dir,
                                     video_type=st.session_state.video_type)
            st.session_state.script = script
            st.session_state.script_confirmed = False
        st.rerun()

    # 脚本预览与编辑
    if st.session_state.script:
        script = st.session_state.script
        st.success(f"✅ 脚本已生成: **{script.get('title', '')}**")

        segs = script.get("segments", [])
        total_dur = sum(s.get("estimated_duration", 0) for s in segs)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("段落数", len(segs))
        with col2:
            st.metric("预估时长", f"{total_dur // 60}分{total_dur % 60}秒")
        with col3:
            if script.get("video_type") == "ppt":
                st.metric("幻灯片", len(script.get("slides", [])))
            else:
                st.metric("场景配图", len(script.get("scenes", [])))

        st.subheader("出处标注")
        st.info(script.get("source_attribution", ""))

        st.subheader("旁白段落（可编辑）")
        for i, seg in enumerate(segs):
            with st.expander(f"段落 {seg['id']} ({seg.get('estimated_duration', '?')}s)", expanded=False):
                new_text = st.text_area(
                    "旁白文本",
                    value=seg.get("narration_text", ""),
                    key=f"seg_edit_{seg['id']}",
                    height=100,
                    label_visibility="collapsed",
                )
                st.session_state.script["segments"][i]["narration_text"] = new_text

                if st.button(f"🔄 重新生成此段", key=f"regen_{seg['id']}"):
                    with st.spinner("重新生成中..."):
                        from src.script_generator import regenerate_segment
                        new_text_ai = regenerate_segment(
                            seg.get("narration_text", ""),
                            st.session_state.image_style,
                        )
                        st.session_state.script["segments"][i]["narration_text"] = new_text_ai
                    st.rerun()

        if st.button("✅ 确认脚本，进入下一步", type="primary"):
            st.session_state.script_confirmed = True
            script_path = get_output_dir() / "script.json"
            with open(script_path, "w", encoding="utf-8") as f:
                json.dump(st.session_state.script, f, ensure_ascii=False, indent=2)

            _output_dir = get_output_dir()
            _image_style = st.session_state.image_style
            _video_type = st.session_state.video_type

            if _video_type == "ppt":
                # PPT 模式：并行生成封面 + 幻灯片图片
                slide_count = len(script.get("slides", []))
                with st.spinner(f"正在生成封面和 {slide_count} 张幻灯片图片（约3-5分钟）..."):
                    from concurrent.futures import ThreadPoolExecutor

                    def _gen_covers():
                        from src.cover_generator import generate_cover_prompts, generate_covers
                        output_dir = _output_dir / "covers"
                        prompts = generate_cover_prompts(
                            script.get("title", ""),
                            script.get("description", ""),
                        )
                        covers = generate_covers(prompts, output_dir)
                        return prompts, covers

                    def _gen_slides():
                        from src.image_generator import generate_slide_images
                        output_dir = _output_dir / "slides"
                        slides = script.get("slides", [])
                        images = generate_slide_images(slides, output_dir,
                                                       image_style=_image_style)
                        return slides, images

                    with ThreadPoolExecutor(max_workers=2) as pool:
                        cover_future = pool.submit(_gen_covers)
                        slide_future = pool.submit(_gen_slides)
                        cover_prompts, covers = cover_future.result()
                        slides_info, slide_imgs = slide_future.result()

                    st.session_state.covers = [str(p) for p in covers]
                    st.session_state.cover_prompts = cover_prompts
                    st.session_state.selected_cover = None
                    st.session_state.slide_images = [str(p) if p else None for p in slide_imgs]
                    st.session_state.slide_prompts = slides_info
                    # PPT 模式不需要 scene_images，但清空以防残留
                    st.session_state.scene_images = []
                    st.session_state.selected_scene = None

                ok_count = sum(1 for p in st.session_state.slide_images if p)
                switch_tab(1, f"✅ 脚本已确认！已生成 {ok_count} 张幻灯片。请切换到「② 封面」Tab")
            else:
                # 经典模式：并行生成封面 + 配图（原逻辑）
                with st.spinner("正在并行生成封面和配图（约2-3分钟）..."):
                    from concurrent.futures import ThreadPoolExecutor

                    def _gen_covers():
                        from src.cover_generator import generate_cover_prompts, generate_covers
                        output_dir = _output_dir / "covers"
                        prompts = generate_cover_prompts(
                            script.get("title", ""),
                            script.get("description", ""),
                        )
                        covers = generate_covers(prompts, output_dir)
                        return prompts, covers

                    def _gen_scenes():
                        from src.image_generator import generate_scene_prompts, generate_images
                        output_dir = _output_dir / "images"
                        prompts = generate_scene_prompts(
                            script.get("title", ""),
                            script.get("description", ""),
                            _image_style,
                        )
                        images = generate_images(prompts, output_dir,
                                                 image_style=_image_style)
                        return prompts, images

                    with ThreadPoolExecutor(max_workers=2) as pool:
                        cover_future = pool.submit(_gen_covers)
                        scene_future = pool.submit(_gen_scenes)
                        cover_prompts, covers = cover_future.result()
                        scene_prompts, scenes = scene_future.result()

                    st.session_state.covers = [str(p) for p in covers]
                    st.session_state.cover_prompts = cover_prompts
                    st.session_state.selected_cover = None
                    st.session_state.scene_images = [str(p) for p in scenes]
                    st.session_state.scene_prompts = scene_prompts
                    st.session_state.selected_scene = None
                    # 清空 PPT 残留
                    st.session_state.slide_images = []

                switch_tab(1, "✅ 脚本已确认，封面和配图已生成！请切换到「② 封面」Tab 选择")


# ════════════════════════════════════════════
# Tab ② 封面生成
# ════════════════════════════════════════════
with tabs[1]:
    st.header("封面生成")

    if not st.session_state.script_confirmed:
        st.warning("⚠️ 请先在「① 脚本」Tab 中生成并确认脚本")
    else:
        script = st.session_state.script

        # 参考图上传
        ref_cover_col1, ref_cover_col2 = st.columns([2, 1])
        with ref_cover_col1:
            ref_cover_file = st.file_uploader(
                "🖼️ 上传参考图（可选，AI 将参考其风格）",
                type=["jpg", "jpeg", "png"],
                key="ref_cover_upload",
            )
        with ref_cover_col2:
            if st.session_state._ref_cover_path and Path(st.session_state._ref_cover_path).exists():
                st.image(st.session_state._ref_cover_path, caption="当前参考图", width=120)

        if ref_cover_file:
            _ref_key = f"{ref_cover_file.name}_{ref_cover_file.size}"
            if st.session_state.get("_ref_cover_sig") != _ref_key:
                st.session_state._ref_cover_sig = _ref_key
                ref_dir = get_output_dir() / "ref"
                ref_dir.mkdir(parents=True, exist_ok=True)
                ref_path = ref_dir / "ref_cover.jpg"
                with open(ref_path, "wb") as f:
                    f.write(ref_cover_file.getbuffer())
                st.session_state._ref_cover_path = str(ref_path)
                st.rerun()

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            generate_disabled = bool(st.session_state.covers) and not st.session_state.get("_regen_cover")
            if st.button("🎨 生成 2 张封面候选", disabled=False if st.session_state.get("_regen_cover") else generate_disabled):
                st.session_state._regen_cover = False
                with st.spinner("正在生成封面（约1-2分钟）..."):
                    from src.cover_generator import generate_cover_prompts, generate_covers, enhance_prompt_with_reference
                    output_dir = get_output_dir() / "covers"
                    prompts = generate_cover_prompts(
                        script.get("title", ""),
                        script.get("description", ""),
                    )
                    # 参考图增强
                    if st.session_state._ref_cover_path:
                        for p in prompts:
                            if isinstance(p, dict):
                                p["prompt"] = enhance_prompt_with_reference(
                                    p["prompt"], Path(st.session_state._ref_cover_path)
                                )
                    covers = generate_covers(prompts, output_dir)
                    st.session_state.covers = [str(p) for p in covers]
                    st.session_state.cover_prompts = prompts
                    st.session_state.selected_cover = None  # 重置选择
                st.rerun()

        with btn_col2:
            if st.session_state.covers:
                if st.button("🔄 重新生成封面"):
                    st.session_state._regen_cover = True
                    st.session_state.covers = []
                    st.session_state.selected_cover = None
                    st.rerun()

        if st.session_state.covers:
            st.subheader("选择封面")
            cols = st.columns(len(st.session_state.covers))
            for i, cover_path in enumerate(st.session_state.covers):
                with cols[i]:
                    style_name = ""
                    if i < len(st.session_state.cover_prompts):
                        p = st.session_state.cover_prompts[i]
                        style_name = p.get("style", "") if isinstance(p, dict) else ""
                    caption = f"封面 {i+1}" + (f" ({style_name})" if style_name else "")
                    st.image(cover_path, caption=caption, use_container_width=True)
                    if st.button(f"✅ 选择此封面", key=f"cover_pick_{i}"):
                        st.session_state.selected_cover = cover_path
                        switch_tab(2, "✅ 封面已选择！请切换到「③ 素材」Tab")

            if st.session_state.selected_cover:
                st.success(f"✅ 已选择封面: {Path(st.session_state.selected_cover).name}")

        # 手动上传封面
        st.divider()
        uploaded_cover = st.file_uploader(
            "📁 或上传自己的封面图片",
            type=["jpg", "jpeg", "png"],
            key="upload_cover",
        )
        if uploaded_cover:
            _cov_key = f"{uploaded_cover.name}_{uploaded_cover.size}"
            if st.session_state.get("_upload_cover_sig") != _cov_key:
                st.session_state._upload_cover_sig = _cov_key
                cover_dir = get_output_dir() / "covers"
                cover_dir.mkdir(parents=True, exist_ok=True)
                upload_path = cover_dir / "uploaded_cover.jpg"
                with open(upload_path, "wb") as f:
                    f.write(uploaded_cover.getbuffer())
                upload_str = str(upload_path)
                if upload_str not in st.session_state.covers:
                    st.session_state.covers.append(upload_str)
                    st.session_state.cover_prompts.append({"style": "手动上传"})
                st.rerun()


# ════════════════════════════════════════════
# Tab ③ 素材生成
# ════════════════════════════════════════════
with tabs[2]:
    st.header("素材生成")

    if not st.session_state.script_confirmed:
        st.warning("⚠️ 请先在「① 脚本」Tab 中生成并确认脚本")
    else:
        script = st.session_state.script

        # ── 配图 / 幻灯片 ──
        if st.session_state.video_type == "ppt":
            # ═══ PPT 模式：幻灯片网格 ═══
            slide_count = len(script.get("slides", []))
            st.subheader(f"🖼️ 幻灯片（{slide_count} 张）")

            if st.session_state.slide_images:
                st.success(f"✅ 已生成 {len(st.session_state.slide_images)} 张幻灯片图片")

                # 网格显示（每行3张）
                slides = script.get("slides", [])
                for row_start in range(0, len(st.session_state.slide_images), 3):
                    row_images = st.session_state.slide_images[row_start:row_start + 3]
                    cols = st.columns(len(row_images))
                    for col_idx, img_path in enumerate(row_images):
                        slide_idx = row_start + col_idx
                        with cols[col_idx]:
                            note = ""
                            if slide_idx < len(slides):
                                note = slides[slide_idx].get("note", "")
                            if img_path:
                                st.image(img_path, caption=f"幻灯片 {slide_idx+1}: {note}",
                                         use_container_width=True)
                            else:
                                st.warning(f"幻灯片 {slide_idx+1} 生成失败")
                            # 单张重新生成
                            if st.button(f"🔄 重新生成", key=f"regen_slide_{slide_idx}"):
                                from src.image_generator import generate_slide_images
                                with st.spinner(f"重新生成幻灯片 {slide_idx+1}..."):
                                    slide_data = slides[slide_idx]
                                    new_imgs = generate_slide_images(
                                        [slide_data],
                                        get_output_dir() / "slides",
                                        image_style=st.session_state.image_style,
                                    )
                                    if new_imgs and new_imgs[0]:
                                        st.session_state.slide_images[slide_idx] = str(new_imgs[0])
                                st.rerun()

                # 全部重新生成
                if st.button("🔄 重新生成全部幻灯片"):
                    with st.spinner(f"重新生成 {slide_count} 张幻灯片（约3-5分钟）..."):
                        from src.image_generator import generate_slide_images
                        output_dir = get_output_dir() / "slides"
                        new_imgs = generate_slide_images(
                            slides, output_dir,
                            image_style=st.session_state.image_style,
                        )
                        st.session_state.slide_images = [str(p) if p else None for p in new_imgs]
                    st.rerun()
            else:
                st.info("幻灯片图片将在脚本确认后自动生成。如果未生成，请点击下方按钮。")
                if st.button(f"🎨 生成 {slide_count} 张幻灯片"):
                    with st.spinner(f"正在生成 {slide_count} 张幻灯片（约3-5分钟）..."):
                        from src.image_generator import generate_slide_images
                        output_dir = get_output_dir() / "slides"
                        slides = script.get("slides", [])
                        imgs = generate_slide_images(
                            slides, output_dir,
                            image_style=st.session_state.image_style,
                        )
                        st.session_state.slide_images = [str(p) if p else None for p in imgs]
                        st.session_state.slide_prompts = slides
                    st.rerun()
        else:
            # ═══ 经典模式：2张选1张（原逻辑） ═══
            st.subheader("🖼️ 配图（2张选1张）")

            # 参考图上传
            ref_scene_col1, ref_scene_col2 = st.columns([2, 1])
            with ref_scene_col1:
                ref_scene_file = st.file_uploader(
                    "🖼️ 上传参考图（可选，AI 将参考其风格）",
                    type=["jpg", "jpeg", "png"],
                    key="ref_scene_upload",
                )
            with ref_scene_col2:
                if st.session_state._ref_scene_path and Path(st.session_state._ref_scene_path).exists():
                    st.image(st.session_state._ref_scene_path, caption="当前参考图", width=120)

            if ref_scene_file:
                _ref_key = f"{ref_scene_file.name}_{ref_scene_file.size}"
                if st.session_state.get("_ref_scene_sig") != _ref_key:
                    st.session_state._ref_scene_sig = _ref_key
                    ref_dir = get_output_dir() / "ref"
                    ref_dir.mkdir(parents=True, exist_ok=True)
                    ref_path = ref_dir / "ref_scene.jpg"
                    with open(ref_path, "wb") as f:
                        f.write(ref_scene_file.getbuffer())
                    st.session_state._ref_scene_path = str(ref_path)
                    st.rerun()

            img_btn_col1, img_btn_col2 = st.columns(2)
            with img_btn_col1:
                gen_disabled = bool(st.session_state.scene_images) and not st.session_state.get("_regen_image")
                if st.button("生成 2 张配图候选", disabled=False if st.session_state.get("_regen_image") else gen_disabled):
                    st.session_state._regen_image = False
                    with st.spinner("正在生成配图（约1-2分钟）..."):
                        from src.image_generator import generate_scene_prompts, generate_images
                        from src.cover_generator import enhance_prompt_with_reference
                        output_dir = get_output_dir() / "images"
                        prompts = generate_scene_prompts(
                            script.get("title", ""),
                            script.get("description", ""),
                            st.session_state.image_style,
                        )
                        # 参考图增强
                        if st.session_state._ref_scene_path:
                            prompts = [
                                enhance_prompt_with_reference(p, Path(st.session_state._ref_scene_path))
                                for p in prompts
                            ]
                        images = generate_images(prompts, output_dir,
                                                  image_style=st.session_state.image_style)
                        st.session_state.scene_images = [str(p) for p in images]
                        st.session_state.scene_prompts = prompts
                        st.session_state.selected_scene = None
                    st.rerun()

            with img_btn_col2:
                if st.session_state.scene_images:
                    if st.button("🔄 重新生成配图"):
                        st.session_state._regen_image = True
                        st.session_state.scene_images = []
                        st.session_state.selected_scene = None
                        st.rerun()

            if st.session_state.scene_images:
                cols = st.columns(len(st.session_state.scene_images))
                for i, img_path in enumerate(st.session_state.scene_images):
                    with cols[i]:
                        st.image(img_path, caption=f"配图 {i+1}", use_container_width=True)
                        if st.button(f"✅ 选择此配图", key=f"scene_pick_{i}"):
                            st.session_state.selected_scene = img_path
                            st.success(f"✅ 已选择配图: {Path(st.session_state.selected_scene).name}")

                if st.session_state.selected_scene:
                    st.success(f"✅ 已选择配图: {Path(st.session_state.selected_scene).name}")

            # 手动上传配图
            uploaded_scene = st.file_uploader(
                "📁 或上传自己的配图",
                type=["jpg", "jpeg", "png"],
                key="upload_scene",
            )
            if uploaded_scene:
                _scn_key = f"{uploaded_scene.name}_{uploaded_scene.size}"
                if st.session_state.get("_upload_scene_sig") != _scn_key:
                    st.session_state._upload_scene_sig = _scn_key
                    img_dir = get_output_dir() / "images"
                    img_dir.mkdir(parents=True, exist_ok=True)
                    upload_path = img_dir / "uploaded_scene.jpg"
                    with open(upload_path, "wb") as f:
                        f.write(uploaded_scene.getbuffer())
                    upload_str = str(upload_path)
                    if upload_str not in st.session_state.scene_images:
                        st.session_state.scene_images.append(upload_str)
                        st.session_state.scene_prompts.append("手动上传")
                    st.rerun()

        # ── 旁白音频 ──
        st.divider()
        st.subheader("🎤 旁白音频")

        # 音色选择 + 试听
        voice_names = list(TTS_VOICES.keys())
        voice_values = list(TTS_VOICES.values())
        current_voice_idx = 0
        if st.session_state.selected_voice in voice_values:
            current_voice_idx = voice_values.index(st.session_state.selected_voice)
        voice_col1, voice_col2 = st.columns([3, 1])
        with voice_col1:
            selected_voice_label = st.selectbox(
                "选择音色",
                voice_names,
                index=current_voice_idx,
                help="选择旁白的声音，男声/女声可选",
            )
            # 立即用 selectbox 返回值更新 session_state（同一轮 script run 内生效）
            st.session_state.selected_voice = TTS_VOICES[selected_voice_label]
        with voice_col2:
            st.markdown("<br>", unsafe_allow_html=True)  # 对齐按钮
            if st.button("🔊 试听", key="voice_preview_btn"):
                from src.audio_generator import preview_voice
                # 优先用克隆音色，否则用 selectbox 当前选中的值（而非 session_state 旧值）
                _pv_voice = st.session_state.cloned_voice_id or TTS_VOICES[selected_voice_label]
                _pv_cloned = bool(st.session_state.cloned_voice_id)
                with st.spinner("生成试听音频..."):
                    preview = preview_voice(_pv_voice, is_cloned=_pv_cloned)
                    st.session_state.voice_preview_bytes = preview

        if st.session_state.voice_preview_bytes:
            st.audio(st.session_state.voice_preview_bytes, format="audio/mp3")

        # ── 自定义音色（语音克隆）──
        with st.expander("🎙️ 自定义音色（上传参考音频克隆声音）"):
            st.caption("上传 10-20 秒清晰语音，AI 将克隆该声音用于旁白生成")

            if st.session_state.cloned_voice_id:
                st.info(f"✅ 已克隆音色: **{st.session_state.cloned_voice_name}** (ID: {st.session_state.cloned_voice_id[:20]}...)")
                if st.button("❌ 清除克隆音色", key="clear_clone"):
                    st.session_state.cloned_voice_id = None
                    st.session_state.cloned_voice_name = None
                    st.rerun()
            else:
                clone_file = st.file_uploader(
                    "上传参考音频",
                    type=["mp3", "wav"],
                    key="voice_clone_upload",
                )
                if clone_file:
                    from pydub import AudioSegment as PydubAudio
                    import io
                    audio_seg = PydubAudio.from_file(io.BytesIO(clone_file.getbuffer()))
                    duration_sec = len(audio_seg) / 1000
                    from config import CLONE_AUDIO_MIN_DURATION, CLONE_AUDIO_MAX_DURATION

                    if duration_sec < CLONE_AUDIO_MIN_DURATION:
                        st.error(f"音频太短（{duration_sec:.1f}s），至少需要 {CLONE_AUDIO_MIN_DURATION} 秒")
                    else:
                        if duration_sec > CLONE_AUDIO_MAX_DURATION:
                            audio_seg = audio_seg[:CLONE_AUDIO_MAX_DURATION * 1000]
                            st.warning(f"音频已截断至 {CLONE_AUDIO_MAX_DURATION} 秒")

                        st.success(f"音频时长: {min(duration_sec, CLONE_AUDIO_MAX_DURATION):.1f} 秒")

                        if st.button("🔬 克隆此声音", key="do_clone", type="primary"):
                            # 保存音频到磁盘
                            clone_dir = get_output_dir() / "clone"
                            clone_dir.mkdir(parents=True, exist_ok=True)
                            clone_path = clone_dir / "reference.mp3"
                            audio_seg.export(str(clone_path), format="mp3")

                            from src.audio_generator import enroll_custom_voice
                            with st.spinner("正在克隆声音（约30秒）..."):
                                voice_id = enroll_custom_voice(clone_path, "myvoice")
                            if voice_id:
                                st.session_state.cloned_voice_id = voice_id
                                st.session_state.cloned_voice_name = clone_file.name
                                st.success(f"✅ 克隆成功！voice_id: {voice_id[:30]}...")
                                st.rerun()
                            else:
                                st.error("❌ 克隆失败，请检查音频质量或 SDK 版本")

        # 确定当前使用的音色参数
        _voice = st.session_state.selected_voice
        _is_cloned = False
        if st.session_state.cloned_voice_id:
            _voice = st.session_state.cloned_voice_id
            _is_cloned = True

        # 批量生成控制
        segs = script.get("segments", [])
        audio_dict = st.session_state.audio_paths
        done_count = sum(1 for s in segs if s["id"] in audio_dict)

        batch_col1, batch_col2 = st.columns([1, 2])
        with batch_col1:
            all_done = done_count == len(segs) and len(segs) > 0
            if st.button("🎙️ 生成全部旁白", disabled=all_done):
                from src.audio_generator import generate_audio
                output_dir = get_output_dir() / "audio"
                status_text = st.empty()
                progress_bar = st.progress(0)

                def on_progress(pct, msg):
                    progress_bar.progress(pct)
                    status_text.text(msg)

                audio_paths = generate_audio(
                    segs, output_dir,
                    voice=_voice, is_cloned=_is_cloned,
                    progress_callback=on_progress,
                )
                # 批量结果写入 dict
                for seg_item, p in zip(segs, audio_paths):
                    st.session_state.audio_paths[seg_item["id"]] = str(p)
                progress_bar.empty()
                status_text.empty()
                st.rerun()
        with batch_col2:
            if len(segs) > 0:
                st.progress(done_count / len(segs))
                st.caption(f"已完成 {done_count}/{len(segs)} 段")

        # 逐段列表
        for i, seg in enumerate(segs):
            seg_id = seg["id"]
            has_audio = seg_id in audio_dict
            seg_text = seg.get("narration_text", "")
            preview_text = seg_text[:60] + "..." if len(seg_text) > 60 else seg_text
            status_icon = "✅" if has_audio else "▶️"
            # 自动展开第一个没有音频的段落
            auto_expand = not has_audio and (
                i == 0 or all(segs[j]["id"] in audio_dict for j in range(i))
            )

            with st.expander(f"{status_icon} 段落 {seg_id}: {preview_text}", expanded=auto_expand):
                new_text = st.text_area(
                    "旁白文本",
                    value=seg_text,
                    key=f"audio_seg_{seg_id}",
                    height=80,
                    label_visibility="collapsed",
                )
                st.session_state.script["segments"][i]["narration_text"] = new_text

                btn_label = "🔄 重新生成" if has_audio else "🎙️ 生成此段"
                if st.button(btn_label, key=f"gen_seg_{seg_id}"):
                    from src.audio_generator import generate_single_audio
                    output_dir = get_output_dir() / "audio"
                    updated_seg = {**seg, "narration_text": new_text}
                    with st.spinner(f"生成段落 {seg_id}..."):
                        result = generate_single_audio(
                            updated_seg, output_dir,
                            voice=_voice, is_cloned=_is_cloned,
                        )
                    if result:
                        st.session_state.audio_paths[seg_id] = str(result)
                    st.rerun()

                if has_audio:
                    st.audio(audio_dict[seg_id], format="audio/mp3")

        # ── BGM ──
        st.divider()
        st.subheader("🎵 背景音乐")
        bgm_option = st.radio(
            "选择 BGM",
            ["不使用 BGM", "上传自己的音乐", "选择预置音乐"],
            horizontal=True,
        )

        if bgm_option == "上传自己的音乐":
            uploaded = st.file_uploader("上传 MP3 文件", type=["mp3", "wav"])
            if uploaded:
                bgm_path = get_output_dir() / "custom_bgm.mp3"
                with open(bgm_path, "wb") as f:
                    f.write(uploaded.getbuffer())
                st.session_state.bgm_path = str(bgm_path)
                st.success("✅ 自定义 BGM 已上传")

        elif bgm_option == "选择预置音乐":
            music_files = list(MUSIC_DIR.glob("*.mp3")) if MUSIC_DIR.exists() else []
            if music_files:
                names = [f.name for f in music_files]
                chosen = st.selectbox("选择预置 BGM", names)
                st.session_state.bgm_path = str(MUSIC_DIR / chosen)
            else:
                st.info("暂无预置音乐，请将 mp3 文件放入 assets/music/ 目录")

        else:
            st.session_state.bgm_path = None


# ════════════════════════════════════════════
# Tab ④ 视频合成
# ════════════════════════════════════════════
with tabs[3]:
    st.header("视频合成")

    # 构建有序音频列表（dict → ordered list）
    segs_for_compose = st.session_state.script.get("segments", []) if st.session_state.script else []
    audio_dict = st.session_state.audio_paths
    audio_paths_ordered = [
        Path(audio_dict[seg["id"]])
        for seg in segs_for_compose
        if seg["id"] in audio_dict
    ]
    all_audio_done = len(segs_for_compose) > 0 and len(audio_paths_ordered) == len(segs_for_compose)

    _is_ppt = st.session_state.video_type == "ppt"

    if _is_ppt:
        has_images = any(p for p in st.session_state.slide_images if p)
        can_compose = has_images and all_audio_done and st.session_state.script_confirmed
    else:
        has_images = bool(st.session_state.selected_scene)
        can_compose = has_images and all_audio_done and st.session_state.script_confirmed

    if not can_compose:
        missing = []
        if not has_images:
            missing.append("幻灯片图片" if _is_ppt else "配图")
        if not all_audio_done:
            done = len(audio_paths_ordered)
            total = len(segs_for_compose)
            missing.append(f"旁白音频 ({done}/{total})")
        if not st.session_state.script_confirmed:
            missing.append("确认脚本")
        st.warning(f"⚠️ 请先完成: {', '.join(missing)}")
    else:
        # 显示合成前的准备状态
        col1, col2, col3 = st.columns(3)
        with col1:
            if _is_ppt:
                valid_slides = sum(1 for p in st.session_state.slide_images if p)
                st.metric("幻灯片", f"{valid_slides} 张")
            else:
                st.metric("配图", Path(st.session_state.selected_scene).name)
        with col2:
            st.metric("旁白段数", len(audio_paths_ordered))
        with col3:
            bgm_name = Path(st.session_state.bgm_path).name if st.session_state.bgm_path else "无"
            st.metric("BGM", bgm_name)

        if st.button("🎬 开始合成视频", type="primary",
                      disabled=bool(st.session_state.video_path)):
            from src.subtitle_generator import generate_subtitles

            output_dir = get_output_dir()
            status_text = st.empty()
            progress_bar = st.progress(0)

            def on_progress(pct, msg):
                progress_bar.progress(pct)
                status_text.text(msg)

            bgm = Path(st.session_state.bgm_path) if st.session_state.bgm_path else None

            if _is_ppt:
                # PPT 模式合成
                from src.video_composer import compose_ppt_video

                # 构建 slide_segment_map
                slides = st.session_state.script.get("slides", [])
                slide_segment_map = {}
                for slide in slides:
                    slide_segment_map[slide["id"]] = slide.get("segment_ids", [])

                # 保留 None 占位（保持 slide_id 与索引的对应关系）
                slide_images_for_compose = [
                    Path(p) if p else None for p in st.session_state.slide_images
                ]

                video_path = compose_ppt_video(
                    slide_images=slide_images_for_compose,
                    audio_paths=audio_paths_ordered,
                    output_path=output_dir / "final_video.mp4",
                    segments=segs_for_compose,
                    slide_segment_map=slide_segment_map,
                    bg_music_path=bgm,
                    progress_callback=on_progress,
                )
            else:
                # 经典模式合成
                from src.video_composer import compose_video

                video_path = compose_video(
                    image_path=Path(st.session_state.selected_scene),
                    audio_paths=audio_paths_ordered,
                    output_path=output_dir / "final_video.mp4",
                    segments=segs_for_compose,
                    bg_music_path=bgm,
                    progress_callback=on_progress,
                )

            st.session_state.video_path = str(video_path)

            # 生成字幕
            status_text.text("生成字幕...")
            subtitle_path = generate_subtitles(
                segments=segs_for_compose,
                audio_paths=audio_paths_ordered,
                output_path=output_dir / "subtitles.srt",
            )
            st.session_state.subtitle_path = str(subtitle_path)
            progress_bar.empty()
            status_text.empty()
            switch_tab(4, "✅ 视频合成完成！请切换到「⑤ 输出」Tab 下载")

        if st.session_state.video_path:
            st.success("✅ 视频合成完成！")
            st.video(st.session_state.video_path)


# ════════════════════════════════════════════
# Tab ⑤ 输出与下载
# ════════════════════════════════════════════
with tabs[4]:
    st.header("输出与下载")

    if not st.session_state.video_path:
        st.warning("⚠️ 请先在「④ 合成」Tab 中完成视频合成")
    else:
        script = st.session_state.script or {}

        # 元数据
        st.subheader("📋 元数据")
        st.text(f"标题: {script.get('title', '')}")
        st.text(f"描述:\n{script.get('description', '')}")
        st.text(f"出处: {script.get('source_attribution', '')}")

        # 保存元数据文件
        metadata_text = (
            f"标题: {script.get('title', '')}\n\n"
            f"描述:\n{script.get('description', '')}\n\n"
            f"出处: {script.get('source_attribution', '')}\n\n"
            f"标签: AI, 知识分享, 深度解读\n"
        )
        metadata_path = get_output_dir() / "metadata.txt"
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(metadata_text)

        # 下载按钮
        st.subheader("📥 下载")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if Path(st.session_state.video_path).exists():
                with open(st.session_state.video_path, "rb") as f:
                    st.download_button(
                        "📥 下载视频",
                        data=f.read(),
                        file_name="final_video.mp4",
                        mime="video/mp4",
                        type="primary",
                    )

        with col2:
            if st.session_state.selected_cover and Path(st.session_state.selected_cover).exists():
                with open(st.session_state.selected_cover, "rb") as f:
                    st.download_button(
                        "📥 下载封面",
                        data=f.read(),
                        file_name=Path(st.session_state.selected_cover).name,
                        mime="image/jpeg",
                    )

        with col3:
            if st.session_state.subtitle_path and Path(st.session_state.subtitle_path).exists():
                with open(st.session_state.subtitle_path, "r", encoding="utf-8") as f:
                    st.download_button(
                        "📥 下载字幕",
                        data=f.read().encode("utf-8"),
                        file_name="subtitles.srt",
                        mime="text/plain",
                    )

        with col4:
            st.download_button(
                "📥 下载元数据",
                data=metadata_text.encode("utf-8"),
                file_name="metadata.txt",
                mime="text/plain",
            )

        st.divider()
        st.info("💡 请手动将视频上传到 B站/YouTube，上传时填写元数据中的标题和描述。")
        st.text(f"📂 输出目录: {get_output_dir()}")
