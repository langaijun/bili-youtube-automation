# 🎬 半自动视频制作 Agent

> 输入内容 → AI 生成脚本 → 配图+旁白 → 合成视频  
> 适用于 B站/YouTube 深度解读类视频

## 功能特性

- **AI 脚本生成** — 输入想法/书籍观点，千问 Qwen 自动优化成结构化视频脚本
- **AI 封面生成** — 生成 2 张候选封面，手动选择最佳
- **AI 配图生成** — 通义万相生成配图，支持多种风格预设（极简插画/电影感/涂鸦等）
- **AI 旁白生成** — CosyVoice TTS 生成中文语音旁白
- **自动字幕** — 根据音频时长自动生成 .srt 字幕文件
- **视频合成** — MoviePy 合成 1920×1080 视频，带 Ken Burns 动效
- **BGM 可选** — 支持上传自定义音乐或使用预置免版权音乐
- **局部重做** — 支持编辑单段旁白并重新生成，不影响其他内容

## 技术栈

| 组件 | 技术 |
|------|------|
| AI 脚本 | 千问 Qwen Max (DashScope OpenAI-compatible) |
| 图片生成 | 通义万相 Wanx 2.1 |
| 语音合成 | CosyVoice (DashScope) |
| 视频合成 | MoviePy + FFmpeg |
| 图片处理 | Pillow |
| Web 界面 | Streamlit |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 DashScope API Key
# 获取地址: https://dashscope.console.aliyun.com/apiKey
```

### 3. 启动应用

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`

### 4. 使用流程

1. **① 脚本** — 输入内容，选择图片风格，AI 生成脚本，可编辑每段旁白
2. **② 封面** — AI 生成 2 张封面候选，选择 1 张
3. **③ 素材** — AI 生成 2 张配图（选 1 张）+ 生成全部旁白 + 选择 BGM
4. **④ 合成** — 一键合成视频（配图 + Ken Burns + 旁白 + BGM）
5. **⑤ 输出** — 下载视频/封面/字幕/元数据，手动上传 B站/YouTube

## 项目结构

```
bili-youtube-automation/
├── app.py                     # Streamlit 主界面
├── config.py                  # 全局配置
├── requirements.txt
├── .env.example               # API Key 模板
├── src/
│   ├── script_generator.py    # 脚本生成（Qwen）
│   ├── cover_generator.py     # 封面生成（Qwen + 万相）
│   ├── image_generator.py     # 配图生成（万相）
│   ├── audio_generator.py     # 旁白生成（CosyVoice）
│   ├── subtitle_generator.py  # 字幕生成
│   └── video_composer.py      # 视频合成（MoviePy）
├── assets/
│   ├── fonts/                 # 中文字体
│   └── music/                 # 预置BGM
└── output/                    # 生成的视频/图片/音频（不上传 git）
```

## 环境要求

- Python 3.10+
- FFmpeg（通过 `pip install imageio-ffmpeg` 自动安装）
- 中文字体（已内置 SimHei）
- DashScope API Key（[获取地址](https://dashscope.console.aliyun.com/apiKey)）

## 注意事项

- 生成的视频在 `output/` 目录，已加入 `.gitignore` 不会上传到代码仓库
- 脚本内容建议标注原作者和出处，避免版权问题
- AI 生成的配图不包含原作者图片或书籍封面
- 预置 BGM 来自 Pixabay（免版权），也可上传自己的音乐

## License

MIT
