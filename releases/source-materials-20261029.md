# 依赖源码资料补充 · 2026-10-29

本轮完成 DIST-01／02／03 的版本、源码与许可资料核查。原 rc.1 安装包、
四个外部程序及其依赖版本均未修改；未推送、上传 Release 或操作 PR。

## 保留的交付物

所有附件均在项目 `dist` 目录；它们是源码资料，不是安装包，不需要安装到 DSH。

| 附件 | 大小 | 作用 |
|---|---:|---|
| `dsh-cyber-amber-0.2.1-rc.1-upstream-sources.tar.gz` | 原文件保持不变 | 四个主项目源码快照及构建配方 |
| `dsh-cyber-amber-0.2.1-rc.1-third-party-sources-final-20261029.tar.gz` | 291,703,528 字节 | 669 项依赖源码或构建／署名资料，共 674 个文件 |
| `dsh-cyber-amber-0.2.1-rc.1-ffmpeg-native-sources-20261029.tar.gz` | 2,060,107,056 字节 | 103 份原生依赖源码、核查结果及上游构建记录，共 117 个文件 |

两个新增附件的 SHA256 见 `dist/SHA256SUMS-source-materials-20261029.txt`，
同样记录在 [机器可读回执](source-materials-20261029.json) 中。

## 实际完成的核查

- FFmpeg：对应上游构建 `40502414924` 的完整下载缓存 SHA256 与上游一致；
  提取 103 份选定源码，未缺项。检查根目录／子目录 Git HEAD、LAME SVN 7113；
  AMF 缓存按配方移除了 Git 元数据，其 578 个文件与指定提交的完整文件树一致。
- Gifski：保留完整 103 项 Cargo.lock 中的依赖源码，注册表源码按锁文件哈希验证；
  Rust 编译器版本和 imagequant 引用与二进制证据对应，保留相关许可与署名。
- yt-dlp：保留 21 份按 Windows 构建锁文件匹配的 Python 源码包、自定义 PyInstaller
  源码与构建资料、CPython 完整源码、18 项 Python／原生依赖源码记录。
  curl 的九份原生源码按配方 SHA256 验证；部分 CPython 原生版本来自构建配方，
  没有将其冒充为独立运行时测量结果。
- 另保留 FFmpeg 依赖三个 Cargo.lock 引用的 635 项注册表来源，跨锁重复项合并。
- 两个新增附件逐文件比对内置清单的大小和 SHA256；6 项离线回归测试全部通过，
  无跳过；158 个固定外部程序及支持文件通过完整性检查。

这些资料采用保守的依赖全集，包含可选、测试、构建和其他平台条目。
它不是精确的静态链接清单，不声称完成逐字节重编译或法律合规认证。

## 清理与复验

已删除 2.24GB 的外层下载缓存；最终附件校验后，又清掉 774 个重复源码缓存／
中间附件，合计 2,503,427,485 字节。两个最终源码附件仍需保留，合计约 2.35GB。
用户原片和原 rc.1／0.2.0 发行文件未动。

保留一个清理失败残留：`.validation/distribution/tmpk9mwyom0/wc.db`，446,464 字节。
当时数据库连接未关闭，Windows 拒绝删除；已停止删除该路径，用户可手动移除该目录。
脚本已修正连接关闭逻辑，后续实际核查未重现该问题。

离线复验（Python 3.11+）：

```powershell
python scripts/source_materials.py --verify 'dist/dsh-cyber-amber-0.2.1-rc.1-third-party-sources-final-20261029.tar.gz'
python scripts/source_materials.py --verify 'dist/dsh-cyber-amber-0.2.1-rc.1-ffmpeg-native-sources-20261029.tar.gz'
python scripts/audit-distribution.py --sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-upstream-sources.tar.gz' --materials-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-third-party-sources-final-20261029.tar.gz' --native-sidecar 'dist/dsh-cyber-amber-0.2.1-rc.1-ffmpeg-native-sources-20261029.tar.gz'
python -m unittest discover -s test -p test_source_materials.py -v
```

需要重新生成资料时，分别用 `source_materials.py --restore <附件>` 恢复上述两个
附件的工作缓存。只恢复不透明源码压缩包和构建记录，不解包执行源码、不覆盖已有不同内容。

## 尚未完成的发布步骤

`publication_ready` 仍为 `false`。目前剩余 DIST-04：冻结的 rc.1 安装包未包含
本轮新增声明，需使用新版本号制作并验收新候选包，不能覆盖原包。
这些本地资料不代表用户批准任何公开操作；具体发布内容与操作仍须用户审核同意。
