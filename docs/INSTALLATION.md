# 0.2.1 安装与验收

平台：Windows x64，最低系统为 Windows 10 22H2。实际验证宿主为 DSH 0.2.1-rc.3；
其他宿主版本未验证。四个程序路径留空使用内置的固定版本。

## 本地安装

在 DSH 可用的终端执行；下面路径需替换为自己保存安装包的位置。
已安装旧版时，先在插件页面记下自己的配置，再移除旧包并重新添加：

```powershell
dsh plugin --profile desktop remove dsh-cyber-amber
dsh plugin --profile desktop add 'file:F:/Project/03-Tools-Automation/DSH-plugin/dsh-cyber-amber/dist/dsh-cyber-amber-0.2.1.tgz'
```

首次安装只执行 add。维护者不会代替用户操作实际 desktop profile。
安装前使用 `Get-FileHash -Algorithm SHA256 <安装包>` 对照 `SHA256SUMS-0.2.1.txt`。
安装后若工具未出现，请刷新宿主或新建会话。

## Release 发布后安装

下方链接在 v0.2.1 Release 发布后生效，本地准备阶段不会自动创建 Release：

```powershell
dsh plugin --profile desktop add 'https://github.com/MagneticLine/dsh-cyber-amber/releases/download/v0.2.1/dsh-cyber-amber-0.2.1.tgz'
```

只安装 tgz；GitHub 自动生成的 Source code 包不包含固定二进制。
另外三个源码附件用于源码与许可资料查阅，不需要安装到 DSH。

## 给 DSH 的验收提示词

> 请核对赛博琥珀的安装版本为 0.2.1，四个程序路径留空时应使用内置版。
> 不修改权限、不提权、不安装额外依赖。
> 用 amber_download_video 下载 BV1RwnQ6sEd5，检查 has_audio 与 audio_codec。
> 复用下载文件，用 amber_make_gif 制作 2–6 秒、最大 3MB 的 GIF。
> 检查 640×400、20fps、80 帧、4 秒、无限循环；允许 Q/L 自动降低，M 应仍为 75。
> 极小体积上限应返回 needs_adjustment，不得擅自改变尺寸、帧率或片段。
> 报告实际结果、warnings 和未验证内容。不要上传、发评论、发布或操作 GitHub。

## 维护者复验

先核对 Python 3.11+、Node、npm 和 DSH 的实际路径与版本，不安装或升级依赖。

```powershell
python scripts/prepare-candidate.py --node '<node.exe>' --npm-cli '<npm-cli.js>' --source-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.2-upstream-sources.tar.gz' --materials-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-third-party-sources-final-20261029.tar.gz' --native-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-ffmpeg-native-sources-20261029.tar.gz'
python scripts/verify-host.py --dsh-node '<DSH安装目录/DeepSeek Harness.exe>' --dsh-cli '<DSH安装目录/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-desktop-host/lib/cli.js>' --package 'dist/dsh-cyber-amber-0.2.1.tgz' --source '<已有的至少10秒MP4绝对路径>'
```

脚本拒绝覆盖已有发行文件；需要重做时应先核对原因和版本，而非删除已有包后盲目重跑。
实际工具验收使用隔离 DSH_HOME 和本机 HTTP 视频源，不修改 desktop profile。
检查 `.validation/candidate-0.2.1/` 的测试数量、跳过数、包内容与宿主报告。
`candidate_ready_for_review=true` 仅表示技术检查通过，不代表用户已批准公开操作。
