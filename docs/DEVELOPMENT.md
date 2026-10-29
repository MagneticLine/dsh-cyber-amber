# 开发说明

## 环境与测试

使用项目声明的 Node 版本。现有工作副本不需要安装 npm 依赖或更换包管理器。

```powershell
node --test 'test/*.test.mjs'
python -m unittest discover -s test -p 'test_*.py' -v
```

Node 测试包含真实 FFmpeg／Gifski 编码，原片由 JavaScript 生成，产物位于 `.validation/tests`。
下载协议 fixture 检查本机 HTTP 编排，不代表外部网站下载成功。
历史验证记录见 [VALIDATION.md](VALIDATION.md)，发行结果见仓库 `releases/`。

## 编码与进程

FFmpeg 解码、截取、缩放和采样后，通过有背压的管道传给 Gifski，
不生成有损中间 MP4 或大量逐帧文件。生产进程由 DSH 的 subprocess 服务管理，
响应取消、超时和插件卸载。

处理与清理同时失败时保留原始错误。进程退出未确认时保留对应目录，
不重试副作用，也不把清理失败报告成成功。

## 打包与宿主检查

从 Git 检出后，用 `python scripts/vendor.py` 按锁定 URL 和哈希准备二进制，
再运行 `node scripts/verify-bundle.mjs`。固定二进制不放入 Git。
构建资料见 [vendor/README.md](../vendor/README.md)。

先核对 Python 3.11+、Node、npm 和 DSH 的实际路径和版本。

```powershell
python scripts/prepare-candidate.py --node '<node.exe>' --npm-cli '<npm-cli.js>' --source-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.2-upstream-sources.tar.gz' --materials-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-third-party-sources-final-20261029.tar.gz' --native-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-ffmpeg-native-sources-20261029.tar.gz'
python scripts/verify-host.py --dsh-node '<DSH安装目录/DeepSeek Harness.exe>' --dsh-cli '<DSH安装目录/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-desktop-host/lib/cli.js>' --package 'dist/dsh-cyber-amber-0.2.1.tgz' --source '<已有的至少10秒MP4绝对路径>'
```

候选脚本不覆盖已有发行文件。已制作的本地审核包需要改动时，先保留旧包、
校验值和报告，再产生新审核版本；已公开文件不可就地替换。
隔离宿主使用独立 DSH_HOME、SDK profile 和本机视频，不操作实际 desktop profile。

## 发布资料

检查实际 tgz 的声明与依赖内容，源码和分发检查见 [DISTRIBUTION.md](DISTRIBUTION.md)。
`candidate_ready_for_review=true` 是技术检查结果，公开操作仍需用户批准。
源码附件、校验值和拟执行动作见 [发布审核入口](../releases/0.2.1-review.md)。
