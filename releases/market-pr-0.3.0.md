收录赛博琥珀：视频下载与 GIF 制作工具

在 `tools` 分类新增 `MagneticLine/dsh-cyber-amber`，提供两个工具：

- `amber_download_video`：下载视频并保留原片，返回本地路径及媒体信息。
- `amber_make_gif`：从视频链接或本地文件选取片段制作 GIF，支持自定义尺寸、帧率、画质和体积上限；指定上限时实测并调整 Q/L，保留尺寸、帧率与片段。

条目使用已发布的 v0.3.0 固定安装链接。支持 Windows x64，内置固定版本的 yt-dlp、FFmpeg／ffprobe 和 Gifski；已完成 DSH 0.2.1-rc.3 隔离宿主验证及实际会话验收。

本 PR 仅新增 `data/plugins/MagneticLine__dsh-cyber-amber.yml`，不修改自动生成的 README。
