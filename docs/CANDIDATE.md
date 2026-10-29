# 0.2.1-rc.1 本地候选版

本轮只做本地修改、Git 提交和安装包验收，不推送、不上传 Release、不操作 PR。
两个工具入口及默认 640／20fps／Q75／M75／L75 不变。

## 本地安装

在 DSH 可用的终端执行（请使用你实际保存安装包的绝对路径）：

```powershell
dsh plugin --profile desktop remove dsh-cyber-amber
dsh plugin --profile desktop add 'file:F:/Project/03-Tools-Automation/DSH-plugin/dsh-cyber-amber/dist/dsh-cyber-amber-0.2.1-rc.1.tgz'
```

这两步由用户执行，维护者的验证脚本只操作独立 DSH_HOME 下的 `amber-rc` profile。
安装前可用 `Get-FileHash -Algorithm SHA256 <安装包>` 对照
`dist/SHA256SUMS-0.2.1-rc.1.txt`；0.2.0 的公开包与校验文件保持原样。
四个程序路径留空使用内置版；如未出现工具，请刷新宿主或新建会话。

## 发给 DSH 的验收提示词

> 请验收本地安装的赛博琥珀 0.2.1-rc.1。先只读确认版本和四个程序路径配置；不要改权限、提权或安装依赖。
> 用 amber_download_video 下载 BV1RwnQ6sEd5，检查本地文件和返回的 has_audio/audio_codec。
> 复用下载结果，用 amber_make_gif 制作 2–6 秒、上限 3MB 的 GIF；检查 640×400、20fps、80帧、4秒及无限循环，Q/L 可自动下调，M 必须仍为75。
> 再试一个明显无法满足的体积上限，应返回 needs_adjustment，不自动缩尺寸或降帧率。
> 检查来源地址不包含鉴权参数；如出现 warnings，请保留并解释，不能把“成品完成”误说成“所有清理成功”。
> 不上传、不发评论、不发布、不修改 GitHub。报告实测结果与未验证内容，试验产物经我确认后清理。

## 维护者复验命令

先核对 Node、npm、Python 和 DSH 的实际路径与版本。本项目不需要安装 npm 依赖；
不要为了运行命令修改全局配置或升级工具。占位符使用本机已验证的路径：

```powershell
python scripts/prepare-candidate.py --node '<node.exe>' --npm-cli '<npm-cli.js>' --source-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-upstream-sources.tar.gz' --materials-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-third-party-sources-final-20261029.tar.gz' --native-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-ffmpeg-native-sources-20261029.tar.gz'
python scripts/verify-host.py --dsh-node '<DSH安装目录/DeepSeek Harness.exe>' --dsh-cli '<DSH安装目录/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-desktop-host/lib/cli.js>' --package 'dist/dsh-cyber-amber-0.2.1-rc.1.tgz' --source '<已有的至少10秒MP4绝对路径>'
```

rc.1 文件已经冻结，准备下一个候选版时须先使用新的版本号，不能覆盖原包。
第一个命令验证依赖、完整测试、实际 tgz 和源码附件，生成版本专属校验值。
第二个命令在项目 `.validation` 下隔离安装候选包，用真实 DSH 工具服务和本机 HTTP 视频源
调用下载器与编码器，无模型调用、无平台联网、无 GUI 操作。成功后清理本次宿主与媒体，保留小型报告。
失败时保留具体日志目录；遇到真正的访问拒绝应停止受阻操作，不修改权限或换目录绕过。

结果在 `.validation/candidate-0.2.1-rc.1/`。检查报告的 status、实际测试数量及跳过数，
不能只看启动退出码。CI 文件只是本地准备，未经远端实际运行不能写成“GitHub CI 已通过”。

## 发布条件

本地功能验收通过不等于可以公开发布。当前分发核查阻塞项见
[DISTRIBUTION.md](DISTRIBUTION.md)。`audit-distribution.py --require-public-ready` 应拒绝通过，
不能用功能测试替代这项核查。只有依赖资料、最终安装包、发布文案和市场条目均完成审查，
并得到用户对具体公开操作的明确同意后，才执行任何远端写入。
