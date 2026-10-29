# 赛博琥珀 · Cyber Amber

给 DeepSeek Harness 提供两个工具：下载视频，或把链接／本地视频的一段制作成高质量 GIF。
文件保存在本地，可由用户保存，也可交给其他插件继续处理。本插件不上传、不评论、不自动发布。

Download a video or make a Gifski GIF from a URL/local clip in DeepSeek Harness.
Optional size limits use measured Q/L adjustments. Windows x64 only; output stays local.

默认：**长边640、20fps、Q75／M75／L75、normal、无限循环**。
不预估后要求逐次确认；未指定体积目标时只编码一次，不自动降质。

## 安装与依赖

当前版本为 **0.2.1**；本地安装与验收见 [docs/INSTALLATION.md](docs/INSTALLATION.md)。
源码资料与安装包检查见 [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md)。
下方固定版本下载链接在对应 Release 发布后生效；本地发布准备不代表已上线。

宿主已验证版本为 DSH 0.2.1-rc.3。Windows x64 自包含包最低系统为 Windows 10 22H2。
宿主提供 `@deepseek-ai/*`，
以下程序及所需DLL已包含在tgz中，不用另装Python、FFmpeg、Gifski或yt-dlp。

| 内置程序 | 用途 | 可选外部覆盖项 |
|---|---|---|
| yt-dlp 2026.10.26目录版 | 解析、下载链接；包含其私有Python运行时 | `ytdlpPath` |
| FFmpeg n9.0.2-36-g6882969ce9共享库版 | 截取、缩放、采样与音视频合并 | `ffmpegPath` |
| 同版ffprobe | 探测原片，读取并验证GIF实际帧数和时长 | `ffprobePath` |
| Gifski 1.34.0 | 高质量GIF编码 | `gifskiPath` |

默认使用包内固定版本，使用前验证SHA256及配套文件；不追随latest，不在安装或首次使用时下载／更新程序。
只有显式填写覆盖路径时才使用用户指定的版本；旧版如果填写过路径，清空四个路径字段才切回内置版。
本包目前不支持Windows ARM64、32位、macOS或Linux安装，后续应分别制作平台包。
不要向本包安装另一份 `@deepseek-ai/*`。

在DSH可用的终端中执行：

```powershell
dsh plugin --profile desktop add 'https://github.com/MagneticLine/dsh-cyber-amber/releases/download/v0.2.1/dsh-cyber-amber-0.2.1.tgz'
```

若提示找不到 `dsh`，请使用DSH安装目录提供的CLI执行同样的参数；不需要另外安装编码器。
也可以从 [Releases](https://github.com/MagneticLine/dsh-cyber-amber/releases) 下载tgz，
核对同页 `SHA256SUMS-0.2.1.txt` 后按本地文件安装：`dsh plugin --profile desktop add 'file:C:/Downloads/dsh-cyber-amber-0.2.1.tgz'`。

安装后若当前会话未显示工具，重启DSH或创建新会话。无需执行安装脚本或给系统临时目录添加权限。
开发后刷新本地安装需先remove再add；仅改源码不会更新宿主拷贝。
请使用Release的完整tgz；Git源码仓库不包含大型二进制，不适合直接作为完整安装包。

## 对话验收

- “下载这个视频，保留原片：BV1RwnQ6sEd5。” → `amber_download_video`
- “把 BV1RwnQ6sEd5 的2到6秒做成GIF，默认参数。” → `amber_make_gif`
- “把 C:\Videos\我的视频.mp4 的00：02到00：06做成GIF。”
- “同一片段不超过3MB；先保留640尺寸和20帧。”
- 若返回 `needs_adjustment`，选择“保持20帧，缩小到建议尺寸再试”等取舍。

## 工具参数

`amber_download_video`：`url` 必填，可为HTTP(S)页面链接、BV号或av号；`output_dir` 可选。
默认取1080p以内最佳可用格式与可用音轨，不下载整个播放列表，成品视频保留。
返回 `has_audio` 及存在时的 `audio_codec`；无音轨的原片也可以成功下载。
返回的 `source` 是适合展示的来源，移除查询凭据和片段，仅保留已知视频定位参数；不保证可作为原下载地址复用。
来源未提供分辨率元数据时允许选择该视频流，下载后用ffprobe报告实际尺寸。

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
尺寸按像素显示比例和直角旋转计算；未知像素比例或非直角旋转明确报错。

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
| `ffmpegPath` / `ffprobePath` / `gifskiPath` / `ytdlpPath` | 空：使用包内固定程序；填写时优先使用该路径 |
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
处理与清理同时失败时保留原始错误并补充清理情况。成品有效但临时目录删除失败时，
成品仍保留，结果包含 `warnings`；未确认进程退出时不自动删除任务目录，也不声称已清理。
输出使用唯一文件名，避免覆盖既有结果。成品长期保留，由用户管理。

`maxSourceMB` 和 `maxOutputMB` 不是峰值磁盘配额，合并、复制及试编码会额外占用空间。
强制结束宿主、断电或系统拒绝清理可能留下 `.amber-*`；当前不自动扫描或删除旧任务，
以免误删其他进程的工作。请在确认相关任务与进程已经停止后，按错误中给出的具体目录手动处理。

## 开发测试

不需要npm安装或更换包管理器。完整源码工作副本使用Node24执行：

```powershell
node --test 'test/*.test.mjs'
```

测试包含真实包内FFmpeg/Gifski编码；测试原片由JavaScript直接生成，工件位于项目 `.validation/tests`，
不要求FFmpeg向系统临时目录写视频。离线下载协议fixture只验证编排，不代表平台联网成功。
DSH隔离验证和平台实测状态见 [docs/VALIDATION.md](docs/VALIDATION.md)。
真实desktop会话还验证了两个工具由模型调用、下载音轨可解码、GIF全部80帧可解码。
本次只实测B站样例和本地视频；其他网站的支持范围由yt-dlp、登录权限及网络情况共同决定。

维护者从Git检出后，执行 `python scripts/vendor.py` 按锁定URL与哈希准备依赖，
再执行 `node scripts/verify-bundle.mjs` 和 `npm pack --pack-destination dist`。
依赖二进制不放入Git，但完整tgz包含它们；请保留发行tgz，必要时可从中恢复vendor目录并按清单校验。
只有维护者显式执行准备脚本才联网，用户安装tgz无需运行该脚本。详见 [vendor/README.md](vendor/README.md)。

本包原创代码为MIT；外部程序各自许可与来源见 [NOTICE.md](NOTICE.md)，
对应源码、依赖和构建资料见 [docs/SOURCES.md](docs/SOURCES.md)。
问题反馈请附DSH版本、操作系统、工具错误码和相关参数，勿附Cookie或带鉴权参数的链接。
