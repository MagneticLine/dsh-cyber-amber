# 赛博琥珀 · Cyber Amber

把视频里喜欢的一段，做成一枚可以保存和分享的 GIF。

赛博琥珀为 DeepSeek Harness 提供视频下载和 GIF 制作能力。把视频链接、BV 号或本地文件交给 DSH，告诉它想保留哪一段、需要什么尺寸和体积即可。

Download videos and turn links or local clips into GIFs in DeepSeek Harness.

## 可以这样说

> 把 BV1RwnQ6sEd5 的 2 到 6 秒做成 GIF。

> 同一片段不要超过 3MB，保持长边 640 和每秒 20 帧。

> 把 C:\Videos\我的视频.mp4 的 00：02 到 00：06 做成 GIF。

> 下载这个视频，保留原片：BV1RwnQ6sEd5。

也可以指定更大的尺寸、不同帧率和画质。制作完成后，文件会保存在当前会话工作目录的 `cyber-amber` 文件夹。

## 安装

**Windows x64 · DSH 0.2.1-rc.3**

在 DSH 终端中执行：

```powershell
dsh plugin --profile desktop add 'https://github.com/MagneticLine/dsh-cyber-amber/releases/download/v0.3.0/dsh-cyber-amber-0.3.0.tgz'
```

也可从 [Releases](https://github.com/MagneticLine/dsh-cyber-amber/releases) 下载后本地安装，详见 [安装说明](docs/INSTALLATION.md)。

## 默认效果

| 参数 | 默认值 |
|---|---|
| 尺寸 | 长边 640，保持原片比例 |
| 帧率 | 每秒 20 帧 |
| 画质 | Q75／M75／L75 |
| 播放 | 无限循环 |
| 片段 | 可指定起止时间，默认最长 30 秒 |

小尺寸或低帧率原片会保持在原片范围内。默认使用 Gifski 编码，可在对话中调整上述参数。

## 控制文件大小

想减小文件时，先指定目标体积，让插件保持当前尺寸、帧率、M 和片段，联动降低 Q/L（默认最低 50）。
若仍超限，再和用户确认缩小尺寸或降低帧率：文字和 UI 优先保尺寸，动作优先保帧率，不要盲目把画质一直往下压。

## 设置

可以在插件设置中调整默认尺寸、帧率、画质及片段时长，也能配置下载代理和 Cookie。
需要登录的视频可提供 Cookie 文件；网站支持由 yt-dlp 提供，B 站已实测。

更多选项见 [参数与配置](docs/REFERENCE.md)。开发和测试资料见 [开发说明](docs/DEVELOPMENT-0.3.md)。

## 许可

插件原创代码使用 MIT；第三方程序的许可与来源见 [NOTICE.md](NOTICE.md) 和 [源码说明](docs/SOURCES.md)。
