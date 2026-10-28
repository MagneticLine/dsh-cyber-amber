# 赛博琥珀 · Cyber Amber

给 DeepSeek Harness 提供两个工具：下载视频，或把链接／本地视频的一段制作成高质量 GIF。
文件保存在本地，可由用户保存，也可交给其他插件继续处理。本插件不上传、不评论、不自动发布。

默认：**长边640、20fps、Q75／M75／L75、normal、无限循环**。
不预估后要求逐次确认；未指定体积目标时只编码一次，不自动降质。

## 安装与依赖

宿主已验证版本为 DSH 0.2.1-rc.3。插件是无 npm 运行时依赖的 ESM bundle，宿主提供 `@deepseek-ai/*`。

| 外部程序 | 用途 | 配置项 |
|---|---|---|
| yt-dlp | 解析、下载链接；本地视频转GIF不需要 | `ytdlpPath` |
| FFmpeg | 截取、等比缩放、帧率采样与音视频合并 | `ffmpegPath` |
| ffprobe | 探测原片，读取并验证GIF实际帧数和时长 | `ffprobePath` |
| Gifski | 高质量GIF编码；开发验证使用1.34.0 | `gifskiPath` |

默认从 PATH 查找；也可在插件配置中填写可执行文件的绝对路径。**不自动安装或更新这些程序**。
Gifski 官方下载见 <https://github.com/ImageOptim/gifski/releases>，
yt-dlp 官方下载见 <https://github.com/yt-dlp/yt-dlp/releases>。
Windows 可使用官方 `yt-dlp.exe`，不必另装 Python。不要向本包安装另一份 `@deepseek-ai/*`。

本机源码安装，在 PowerShell 执行：

```powershell
& 'E:\DeepSeekHarness\resources\runtime\cli\bin\dsh.cmd' plugin --profile desktop add 'file:F:\Project\03-Tools-Automation\DSH-plugin\dsh-cyber-amber'
```

随后在 DSH 插件配置中填写需要的程序路径，再重启 DSH。本项目不会替你修改实际 `desktop` profile。
开发后刷新 `file:` 安装需先 remove 再 add；仅改源码不会更新宿主拷贝。

本机已有FFmpeg和ffprobe，现有Gifski也可直接复用，无需再安装一份；在配置中填写其绝对路径即可。
若使用profile覆盖层，以下是填写形式（把yt-dlp路径替换为你实际保存的位置）：

```yaml
- id: cyber-amber
  name: dsh-cyber-amber
  config:
    ffmpegPath: D:/Environment/FFmpeg/bin/ffmpeg.exe
    ffprobePath: D:/Environment/FFmpeg/bin/ffprobe.exe
    gifskiPath: F:/Project/03-Tools-Automation/QQBot/nonebot/tools/gifski-1.34.0/gifski.exe
    ytdlpPath: F:/Tools/yt-dlp.exe
```

这只是本机配置示例，生产代码未内置上述路径；不要覆盖已有的其他profile条目。

## 对话验收

- “下载这个视频，保留原片：BV1RwnQ6sEd5。” → `amber_download_video`
- “把 BV1RwnQ6sEd5 的2到6秒做成GIF，默认参数。” → `amber_make_gif`
- “把 F:\bilibili\我的视频.mp4 的00：02到00：06做成GIF。”
- “同一片段不超过3MB；先保留640尺寸和20帧。”
- 若返回 `needs_adjustment`，选择“保持20帧，缩小到建议尺寸再试”等取舍。

## 工具参数

`amber_download_video`：`url` 必填，可为HTTP(S)页面链接、BV号或av号；`output_dir` 可选。
默认取1080p以内最佳可用格式与可用音轨，不下载整个播放列表，成品视频保留。

`amber_make_gif`：

| 参数 | 默认与语义 |
|---|---|
| `source` | 必填：视频页面链接、BV号、实际存在的本地路径 |
| `start` / `end` | 默认0到片尾；接受数值秒、小数秒、中英文冒号时间码 |
| `long_edge` | 640；128–1920，不放大原片 |
| `fps` | 20；1–30，且不超过原片平均帧率 |
| `quality` | Q75；1–100，默认L随Q调整 |
| `motion_quality` | M75；1–100，独立于Q/L，不代表帧率百分比 |
| `lossy_quality` | 默认等于Q；可独立指定，不同Q/L的组合不自动改写 |
| `max_size_mb` | 可选，正数；1MB＝1,000,000字节，不填不设体积目标 |
| `min_quality` | 体积搜索最低Q/L，默认50；需用户同意后才继续降低 |
| `output_dir` | 默认会话工作目录下 `cyber-amber`；可覆盖 |

起止时间越界自动贴合片头、片尾，不额外提示；没有有效画面时返回错误。
未指定范围时使用整片，默认最多30秒；超长要求选择片段，不擅自截短。
GIF实际时长按百分之一秒量化；相同画面可能合并为更少的编码帧，不代表改变播放速度。
源视频为VFR时，按其平均帧率限制采样；本版本不做HDR色调映射，HDR输入明确报错。

## 体积目标

指定 `max_size_mb` 后，工具内部复用同一原片实测编码，保持尺寸、帧率、M、时间范围和normal不变。
先试所选Q/L；若超限且Q=L，从该值向下搜索至 `min_quality`，检查相邻整数，最多十次不同参数编码。
不为了填满预算提高质量。默认最低50只是当前样本的画质警戒线，不是普适画质保证；
用户主动选择更低的初始画质时尊重该值。独立Q/L组合不自动修改。

未找到合格结果时返回 `needs_adjustment`：目标字节数、最小实测字节数、实际尝试和三类取舍建议。
这些建议基于像素／帧数趋势或下一档质量，**未编码验证、不保证达标**；AI应询问用户选择，不能自行重试。
不交付超限文件，不偷偷改尺寸、帧率或剪掉片段。搜索不是全参数空间的全局最优证明。
实验依据和建议边界见 [docs/QUALITY.md](docs/QUALITY.md)。

## 配置

配置中心使用以下字段；未提供的值由插件补默认。若通过profile patch覆盖 `config`，
DSH使用整对象替换，请保留你已修改的其他字段。

| 配置项 | 默认 |
|---|---|
| `outputDir` | 空：使用会话工作目录的cyber-amber子目录 |
| `ffmpegPath` / `ffprobePath` / `gifskiPath` / `ytdlpPath` | 空：PATH查找 |
| `cookiesFile` | 空：不带Cookie；需登录时填写Netscape Cookie文件绝对路径 |
| `proxy` | 空：不额外指定下载代理；系统网络路由和环境代理仍可能生效 |
| `sourceHeight` | 1080：下载格式高度上限 |
| `longEdge` / `fps` / `quality` / `motionQuality` | 640／20／75／75 |
| `maxClipSeconds` | 30 |
| `timeoutMs` | 300000：包含排队、下载、探测与所有编码尝试 |
| `maxPending` | 3：一个执行，最多再排队两个 |
| `maxSourceMB` | 512：原片大小上限 |
| `maxOutputMB` | 0：不另设输出保护；非0时超限报错，不自动降质 |

无会话的程序调用必须提供绝对 `output_dir` 或绝对配置 `outputDir`。
Cookie文件只传给yt-dlp，不读取浏览器或其他插件的登录态；登录和站点访问验证仍需用户处理。
详细错误包含阶段、原因和下一步；不把完整日志、二进制、Cookie或CDN鉴权查询串塞进模型上下文。

## 文件与资源

FFmpeg解码／截取／缩放／采样后直接通过背压管道传给Gifski，**无有损中间MP4、CRF或逐帧图片目录**。
所有生产进程通过DSH的subprocess管理，并响应取消、超时及插件卸载。
下载工具成品保留；GIF链接入口的原片、试编码和失败产物在任务结束后清理；本地原片不修改。
输出使用唯一文件名，避免覆盖既有结果。成品长期保留，由用户管理。

## 开发测试

不需要npm安装或更换包管理器。使用Node24，设置开发机Gifski路径后执行：

```powershell
$env:AMBER_TEST_GIFSKI = '你的Gifski绝对路径'
node --test 'test/*.test.mjs'
```

测试包含真实FFmpeg/Gifski编码，离线下载协议fixture只验证编排，**不是平台联网成功的证明**。
DSH隔离验证和平台实测状态见 [docs/VALIDATION.md](docs/VALIDATION.md)。

本包原创代码为MIT；外部程序各自许可与来源见 [NOTICE.md](NOTICE.md)。
