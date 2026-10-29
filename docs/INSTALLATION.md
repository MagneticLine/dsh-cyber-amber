# 安装

适用于 Windows x64，DSH 版本为 0.2.1-rc.3。

## 通过链接安装

在 DSH 终端中执行：

```powershell
dsh plugin --profile desktop add 'https://github.com/MagneticLine/dsh-cyber-amber/releases/download/v0.2.1/dsh-cyber-amber-0.2.1.tgz'
```

## 下载后安装

从 [Releases](https://github.com/MagneticLine/dsh-cyber-amber/releases) 下载 `dsh-cyber-amber-0.2.1.tgz`，然后把下面路径换成文件的实际位置：

```powershell
dsh plugin --profile desktop add 'file:C:/Downloads/dsh-cyber-amber-0.2.1.tgz'
```

安装后若当前会话没有出现工具，刷新 DSH 或新建会话。

## 试一下

安装后可以直接对 DSH 说：

> 把 BV1RwnQ6sEd5 的 2 到 6 秒做成 GIF，大小不要超过 3MB。

或者：

> 下载这个视频，保留原片：BV1RwnQ6sEd5。

默认参数可以在插件设置中修改，具体选项见 [参数与配置](REFERENCE.md)。
