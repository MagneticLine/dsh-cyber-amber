# 验证记录 · 2026-10-28

## 环境

- DSH 0.2.1-rc.3，宿主Node 24.21.0。
- FFmpeg/ffprobe 2025-08-14，提交cdbb5f1b93。
- Gifski 1.34.0，可执行文件SHA256：
  `9da8553cbe71c0facf544634b4e377262ea30d34becdc0ca077306342e776295`。
- 没有安装、升级项目依赖或修改全局工具配置；生产代码无npm依赖。
- 实际desktop profile未改动，未操作DSH或浏览器界面。

## 自动测试

27项通过、0项失败、0项跳过，使用Node自带test runner。

覆盖参数及时间码、质量联动、范围拟合、无放大／补帧、单任务有界队列、队列等待取消、
默认真实编码、手动参数、真实体积超限、试编码清理、单次原片复用、离线下载编排、
缺失依赖、源文件保持不变、总超时与运行中取消、输出目录和两个工具的契约／呈现。

下载成功路径使用离线yt-dlp协议fixture，实际复制已存在的短视频并由真实ffprobe检查。
这证明编排可执行，**不代表yt-dlp或任何网站联网下载已验证**。

## 真实DSH宿主验证

独立 `DSH_HOME` 位于项目 `.validation/dsh-home`。
在一次性 `amber-min`（sdk-minimal）及 `amber-web`（web）profile内，通过官方CLI使用 `file:` 安装。
配置schema可导入，插件schema状态为schema，无本插件诊断错误；web启动无 `did not activate`。
外部程序经过宿主subprocess服务运行，不是测试替身。

实际通过 `ctx.tools.execute` 调用，经过参数、返回值和render校验：

| 场景 | 结果 |
|---|---|
| 本地原片2–3秒，默认参数 | completed；640×400、20帧、1.00秒；Q75/M75/L75；1,064,550字节 |
| 同片2–6秒，不超过3MB | completed；640×400、80帧、4.00秒；Q50/M75/L50；2,990,361字节 |
| 极小且不可满足的预算 | needs_adjustment；包含实际尝试、实测大小及未验证的建议；不交付超限文件 |
| 下载入口，缺失yt-dlp | 明确runtime_missing并提示配置ytdlpPath；没有自动安装或重试 |
| fps传文本而非整数 | DSH返回INVALID_ARGS，未执行工具正文 |
| 正在编码时取消 | 返回cancelled，宿主管理进程结束，无遗留.amber临时目录 |

3MB场景实际尝试Q/L：75、50、62、56、53、51、52，共7次；M、尺寸、帧率及时间范围未改变。
源视频SHA256前后保持：
`d10e2c774ce0a66d4b17af5aa018ea88cf7a4e054602cb0e53168b039d0842ba`。

原始报告保存在本机忽略的 `.validation` 中，不随插件分发。
可复用的离线宿主探针为 `test/host-probe.mjs`，在隔离profile通过额外patch挂载该绝对路径，
提供本地 `source`、`outputDir`、`reportDir`（及可选 `start`/`end`）；探针只做本地调用，不联网下载。
须先安装插件、配置引擎路径，运行后检查 `amber-host-report.json` 的status，而非只看启动退出码。

## 建议依据与磁盘占用

用文字、连续运动、渐变三类两秒合成片，共12次实际编码验证调整方向。
全部试验原片、试编码和失败文件已清理，仅保留小型测量JSON及少量宿主验收GIF。
结果见 [QUALITY.md](QUALITY.md)，生成脚本为 `test/measure-advice.mjs`。

## 尚待用户完成

- 本机尚未找到yt-dlp。真实链接下载与各平台的登录／访问限制尚未验证，所有网站均不标记为已实测。
- 按README安装yt-dlp或配置其现有可执行文件路径；不由开发脚本自动安装。
- 用户实际desktop profile的安装、重启与模型对话验收尚未进行。
- 本项目不验证B站GIF上传限制，不证明bili-whale现已支持图片评论；本轮仅制作本地文件。
