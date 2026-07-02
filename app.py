"""半自动视频制作 Agent - Streamlit 主界面"""
import json
import sys
from pathlib import Path

import streamlit as st

# 确保 src 目录可导入
sys.path.insert(0, str(Path(__file__).parent))

from config import IMAGE_STYLES, DEFAULT_STYLE, OUTPUT_DIR, MUSIC_DIR, TTS_VOICES, TTS_VOICE

st.set_page_config(page_title="半自动视频制作 Agent", page_icon="🎬", layout="wide")
st.title("🎬 半自动视频制作 Agent")
st.caption("输入内容 → AI 生成脚本 → 配图+旁白 → 合成视频 | 适用于 B站/YouTube 深度解读")

# ── Session State 初始化 ──
defaults = {
    "project_name": "",
    "image_style": DEFAULT_STYLE,
    "script": None,
    "script_confirmed": False,
    "covers": [],
    "cover_prompts": [],
    "selected_cover": None,
    "scene_images": [],
    "scene_prompts": [],
    "selected_scene": None,
    "audio_paths": [],
    "selected_voice": TTS_VOICE,
    "audio_generating": False,
    "bgm_path": None,
    "video_path": None,
    "subtitle_path": None,
    "active_tab": 0,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def get_output_dir() -> Path:
    name = st.session_state.project_name or "untitled"
    d = OUTPUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def switch_tab(tab_index: int):
    """切换到指定 Tab"""
    st.session_state.active_tab = tab_index
    st.rerun()


# ── Tab 布局 ──
tab_labels = ["① 脚本", "② 封面", "③ 素材", "④ 合成", "⑤ 输出"]
tabs = st.tabs(tab_labels)

# ════════════════════════════════════════════
# Tab ① 脚本生成
# ════════════════════════════════════════════
with tabs[0]:
    st.header("脚本生成")

    col1, col2 = st.columns(2)
    with col1:
        project_name = st.text_input(
            "项目名称",
            value=st.session_state.project_name,
            placeholder="例如: naval_财富自由解读",
        )
        st.session_state.project_name = project_name

    with col2:
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
            script = generate_script(user_input, image_style, output_dir)
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
            st.toast("✅ 脚本已确认！正在跳转到封面生成...", icon="🎨")
            switch_tab(1)


# ════════════════════════════════════════════
# Tab ② 封面生成
# ════════════════════════════════════════════
with tabs[1]:
    st.header("封面生成")

    if not st.session_state.script_confirmed:
        st.warning("⚠️ 请先在「① 脚本」Tab 中生成并确认脚本")
    else:
        script = st.session_state.script

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            generate_disabled = bool(st.session_state.covers) and not st.session_state.get("_regen_cover")
            if st.button("🎨 生成 2 张封面候选", disabled=False if st.session_state.get("_regen_cover") else generate_disabled):
                st.session_state._regen_cover = False
                with st.spinner("正在生成封面（约1-2分钟）..."):
                    from src.cover_generator import generate_cover_prompts, generate_covers
                    output_dir = get_output_dir() / "covers"
                    prompts = generate_cover_prompts(
                        script.get("title", ""),
                        script.get("description", ""),
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
                        st.toast("✅ 封面已选择！正在跳转到素材生成...", icon="🖼️")
                        switch_tab(2)

            if st.session_state.selected_cover:
                st.success(f"✅ 已选择封面: {Path(st.session_state.selected_cover).name}")


# ════════════════════════════════════════════
# Tab ③ 素材生成
# ════════════════════════════════════════════
with tabs[2]:
    st.header("素材生成")

    if not st.session_state.script_confirmed:
        st.warning("⚠️ 请先在「① 脚本」Tab 中生成并确认脚本")
    else:
        script = st.session_state.script

        # ── 配图 ──
        st.subheader("🖼️ 配图（2张选1张）")

        img_btn_col1, img_btn_col2 = st.columns(2)
        with img_btn_col1:
            gen_disabled = bool(st.session_state.scene_images) and not st.session_state.get("_regen_image")
            if st.button("生成 2 张配图候选", disabled=False if st.session_state.get("_regen_image") else gen_disabled):
                st.session_state._regen_image = False
                with st.spinner("正在生成配图（约1-2分钟）..."):
                    from src.image_generator import generate_scene_prompts, generate_images
                    output_dir = get_output_dir() / "images"
                    prompts = generate_scene_prompts(
                        script.get("title", ""),
                        script.get("description", ""),
                        st.session_state.image_style,
                    )
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

        # ── 旁白音频 ──
        st.divider()
        st.subheader("🎤 旁白音频")

        # 音色选择
        voice_names = list(TTS_VOICES.keys())
        selected_voice_label = st.selectbox(
            "选择音色",
            voice_names,
            index=0,
            help="选择旁白的声音，男声/女声可选",
        )
        st.session_state.selected_voice = TTS_VOICES[selected_voice_label]

        audio_btn_col1, audio_btn_col2 = st.columns(2)
        with audio_btn_col1:
            gen_audio_disabled = bool(st.session_state.audio_paths)
            if st.button("生成全部旁白", disabled=gen_audio_disabled):
                from src.audio_generator import generate_audio
                output_dir = get_output_dir() / "audio"
                status_text = st.empty()
                progress_bar = st.progress(0)

                def on_progress(pct, msg):
                    progress_bar.progress(pct)
                    status_text.text(msg)

                audio_paths = generate_audio(
                    script.get("segments", []),
                    output_dir,
                    voice=st.session_state.selected_voice,
                    progress_callback=on_progress,
                )
                st.session_state.audio_paths = [str(p) for p in audio_paths]
                progress_bar.empty()
                status_text.empty()
                st.rerun()

        # 显示已生成的音频（带播放器）
        if st.session_state.audio_paths:
            segs = script.get("segments", [])
            st.success(f"✅ 已生成 {len(st.session_state.audio_paths)} 段旁白")

            for i, audio_path in enumerate(st.session_state.audio_paths):
                seg = segs[i] if i < len(segs) else {}
                seg_text = seg.get("narration_text", "")[:80] + "..." if len(seg.get("narration_text", "")) > 80 else seg.get("narration_text", "")
                with st.expander(f"段落 {i+1}: {seg_text}", expanded=False):
                    st.audio(audio_path, format="audio/mp3")

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

    can_compose = (
        st.session_state.selected_scene
        and st.session_state.audio_paths
        and st.session_state.script_confirmed
    )

    if not can_compose:
        missing = []
        if not st.session_state.selected_scene:
            missing.append("配图")
        if not st.session_state.audio_paths:
            missing.append("旁白音频")
        if not st.session_state.script_confirmed:
            missing.append("确认脚本")
        st.warning(f"⚠️ 请先完成: {', '.join(missing)}")
    else:
        # 显示合成前的准备状态
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("配图", Path(st.session_state.selected_scene).name)
        with col2:
            st.metric("旁白段数", len(st.session_state.audio_paths))
        with col3:
            bgm_name = Path(st.session_state.bgm_path).name if st.session_state.bgm_path else "无"
            st.metric("BGM", bgm_name)

        if st.button("🎬 开始合成视频", type="primary",
                      disabled=bool(st.session_state.video_path)):
            from src.video_composer import compose_video
            from src.subtitle_generator import generate_subtitles

            output_dir = get_output_dir()
            status_text = st.empty()
            progress_bar = st.progress(0)

            def on_progress(pct, msg):
                progress_bar.progress(pct)
                status_text.text(msg)

            bgm = Path(st.session_state.bgm_path) if st.session_state.bgm_path else None

            video_path = compose_video(
                image_path=Path(st.session_state.selected_scene),
                audio_paths=[Path(p) for p in st.session_state.audio_paths],
                output_path=output_dir / "final_video.mp4",
                bg_music_path=bgm,
                progress_callback=on_progress,
            )
            st.session_state.video_path = str(video_path)

            # 生成字幕
            status_text.text("生成字幕...")
            subtitle_path = generate_subtitles(
                segments=st.session_state.script.get("segments", []),
                audio_paths=[Path(p) for p in st.session_state.audio_paths],
                output_path=output_dir / "subtitles.srt",
            )
            st.session_state.subtitle_path = str(subtitle_path)
            progress_bar.empty()
            status_text.empty()
            st.toast("✅ 视频合成完成！正在跳转到输出...", icon="📥")
            switch_tab(4)

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
