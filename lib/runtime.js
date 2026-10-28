import { pipeline } from 'node:stream/promises'
import { AmberError } from './options.js'

export function collectedText(reader) {
  const result = reader?.readFrom(0)
  return typeof result === 'string' ? result : result?.text || ''
}

function detail(reader) {
  return collectedText(reader).trim().split(/\r?\n/).filter(Boolean).slice(-3).join(' ')
    .replace(/https?:\/\/[^\s<>]+/g, value => {
      try { const url = new URL(value); return url.origin + url.pathname } catch { return '[URL]' }
    })
    .replace(/(cookie|authorization|sessdata|bili_jct)\s*[:=]\s*\S+/gi, '$1=[redacted]')
    .slice(-900)
}

export class Runtime {
  constructor(subprocess) { this.subprocess = subprocess }

  async executable(configured, name, signal) {
    signal.throwIfAborted()
    try {
      return await this.subprocess.resolveExecutable(configured || name)
    } catch (error) {
      signal.throwIfAborted()
      throw new AmberError('runtime_missing', `找不到${name}；请安装它或在插件配置中填写${name === 'yt-dlp' ? 'ytdlp' : name}Path绝对路径，然后重试。`)
    }
  }

  spawn(argv, cwd, signal, stdio = {}) {
    signal.throwIfAborted()
    return this.subprocess.spawn({ argv: argv.map(String), cwd,
      stdio: { stdin: 'ignore', stdout: { maxBytes: 1024 * 1024 },
        stderr: { maxBytes: 64 * 1024 }, ...stdio }, graceMs: 1000, signal })
  }

  async stop(handle) {
    if (!handle) return
    handle.terminate()
    const outcomes = await Promise.allSettled([handle.done, handle.waitForExit()])
    if (outcomes[1].status === 'rejected') {
      throw new AmberError('process_cleanup_failed', '宿主未能确认子进程已结束；请检查DSH日志，确认进程停止后再重试。')
    }
  }

  async run(argv, { cwd, signal, stage }) {
    let handle
    try {
      handle = this.spawn(argv, cwd, signal)
      const outcome = await handle.done
      signal.throwIfAborted()
      if (outcome.exitCode !== 0) {
        throw new AmberError(`${stage}_failed`, `${stage}阶段失败（退出码${outcome.exitCode}）：${detail(handle.collected?.stderr) || '无错误详情'}。请检查输入、登录状态或程序配置后重试。`)
      }
      if (handle.collected?.stdout?.readFrom(0)?.lossy) {
        throw new AmberError('output_truncated', `${stage}阶段的输出超出读取上限；请使用单个视频或更短片段。`)
      }
      return collectedText(handle.collected?.stdout)
    } finally { await this.stop(handle) }
  }

  async encode(ffmpeg, gifski, source, output, params, { cwd, signal }) {
    const controller = new AbortController()
    const combined = AbortSignal.any([signal, controller.signal])
    let producer, consumer
    try {
      consumer = this.spawn([gifski, '--quiet', '--quality', params.quality,
        '--motion-quality', params.motion_quality, '--lossy-quality', params.lossy_quality,
        '--fps', params.fps, '--width', params.width, '--height', params.height,
        '--repeat', 0, '--y4m-color-override', 'bt709', '--output', output, '-'], cwd, combined,
      { stdin: 'pipe', stdout: 'ignore' })
      producer = this.spawn([ffmpeg, '-hide_banner', '-v', 'error', '-nostdin', '-threads', 2,
        '-ss', params.start, '-t', params.duration_seconds, '-i', source, '-an', '-sn',
        '-vf', `setpts=PTS-STARTPTS,fps=${params.fps},scale=${params.width}:${params.height}:flags=lanczos:out_color_matrix=bt709,setsar=1`,
        '-pix_fmt', 'yuv444p', '-f', 'yuv4mpegpipe', '-'], cwd, combined, { stdout: 'pipe' })
      if (!producer.stdout || !consumer.stdin) throw new AmberError('pipe_unavailable', 'DSH未提供视频管道；请检查subprocess服务版本。')
      const [, produced, consumed] = await Promise.all([
        pipeline(producer.stdout, consumer.stdin, { signal: combined }), producer.done, consumer.done,
      ])
      signal.throwIfAborted()
      if (produced.exitCode !== 0 || consumed.exitCode !== 0) {
        throw new AmberError('encode_failed', `编码失败：${detail(consumer.collected?.stderr) || detail(producer.collected?.stderr)}。请检查原视频与Gifski版本。`)
      }
    } catch (error) {
      signal.throwIfAborted()
      if (error instanceof AmberError) throw error
      throw new AmberError('encode_failed', `FFmpeg与Gifski管道中断：${detail(consumer?.collected?.stderr) || detail(producer?.collected?.stderr) || error.code || 'pipe_error'}。请检查原视频或缩短片段。`)
    } finally {
      controller.abort()
      const stopped = await Promise.allSettled([this.stop(producer), this.stop(consumer)])
      const failed = stopped.find(result => result.status === 'rejected')
      if (failed) throw failed.reason
    }
  }
}

export class JobQueue {
  constructor(limit = 3) { this.limit = limit; this.count = 0; this.active = false; this.waiting = [] }

  release() {
    this.count--
    const next = this.waiting.shift()
    if (next) { next.signal.removeEventListener('abort', next.abort); next.resolve() }
    else this.active = false
  }

  async run(signal, body) {
    signal.throwIfAborted()
    if (this.count >= this.limit) throw new AmberError('queue_full', '视频任务队列已满，请等待当前任务完成后再试。')
    this.count++
    if (this.active) {
      await new Promise((resolve, reject) => {
        const item = { resolve, signal, abort: () => {
          const index = this.waiting.indexOf(item)
          if (index < 0) return
          this.waiting.splice(index, 1)
          this.count--
          reject(signal.reason)
        } }
        this.waiting.push(item)
        signal.addEventListener('abort', item.abort, { once: true })
        if (signal.aborted) item.abort()
      })
    } else this.active = true
    try { signal.throwIfAborted(); return await body() } finally { this.release() }
  }
}
