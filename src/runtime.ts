import { pipeline } from 'node:stream/promises'
import { basename } from 'node:path'
import { AmberError, addCleanup } from './options.js'
import { bundledExecutable } from './binaries.js'
import type { BundleOptions } from './binaries.js'
import type { CollectedReader, EncodeParams, ProcessHandle, ProcessStdio, RuntimeContext, SubprocessAdapter } from './runtime-types.js'

export type { CollectedReader, EncodeParams, ProcessHandle, RuntimeContext, SubprocessAdapter } from './runtime-types.js'

export function collectedText(reader?: CollectedReader): string {
  const result = reader?.readFrom(0)
  return typeof result === 'string' ? result : result?.text || ''
}

function detail(reader?: CollectedReader): string {
  return collectedText(reader)
    .replace(/\b(cookie|authorization)\s*[:=][^\r\n]*/gi, '$1=[redacted]')
    .trim().split(/\r?\n/).filter(Boolean).slice(-8).join(' ')
    .replace(/https?:\/\/[^\s<>]+/g, value => {
      try { const url = new URL(value); return url.origin + url.pathname } catch { return '[URL]' }
    })
    .replace(/(cookie|authorization|sessdata|bili_jct)\s*[:=]\s*\S+/gi, '$1=[redacted]')
    .slice(-1600)
}

function errorCode(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null || !('code' in error)) return undefined
  return typeof error.code === 'string' ? error.code : undefined
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function processFailure(stage: string, message: string, executable: string, cwd: string): AmberError {
  if (/permission denied|access is denied|拒绝访问|\bEACCES\b|\bEPERM\b/i.test(message)) {
    return new AmberError('permission_denied', `${basename(executable)}在${stage}阶段被系统拒绝访问。工作目录：${cwd}。详情：${message}。请检查该目录对当前用户的访问权限及程序级防护记录；插件不会自动改权限、更换目录或重试。`)
  }
  return new AmberError(`${stage}_failed`, `${basename(executable)}在${stage}阶段失败：${message}。请检查输入、登录状态或程序配置后重试。`)
}

export class Runtime {
  constructor(readonly subprocess: SubprocessAdapter, readonly bundleOptions: BundleOptions = {}) {}

  async executable(configured: string | undefined, name: string, signal: AbortSignal): Promise<string> {
    signal.throwIfAborted()
    // An explicit override is authoritative; never silently replace it with another version.
    if (!configured) {
      const bundled = await bundledExecutable(name, this.bundleOptions)
      signal.throwIfAborted()
      if (bundled) return this.subprocess.resolveExecutable(bundled)
    }
    try {
      return await this.subprocess.resolveExecutable(configured || name)
    } catch {
      signal.throwIfAborted()
      throw new AmberError('runtime_missing', `找不到${name}；请安装它或在插件配置中填写${name === 'yt-dlp' ? 'ytdlp' : name}Path绝对路径，然后重试。`)
    }
  }

  spawn(argv: readonly (string | number)[], cwd: string, signal: AbortSignal, stdio: ProcessStdio = {}): ProcessHandle {
    signal.throwIfAborted()
    return this.subprocess.spawn({ argv: argv.map(String), cwd,
      stdio: { stdin: 'ignore', stdout: { maxBytes: 1024 * 1024 },
        stderr: { maxBytes: 64 * 1024 }, ...stdio }, graceMs: 1000, signal })
  }

  async stop(handle?: ProcessHandle): Promise<void> {
    if (!handle) return
    // Even terminate() can fail. Still ask the host whether the process exited.
    try { handle.terminate() } catch { /* waitForExit is authoritative */ }
    try { await handle.waitForExit() }
    catch {
      const error = new AmberError('process_cleanup_failed', '宿主未能确认子进程已结束；请检查DSH日志，确认进程停止后再重试。')
      error.processesUnconfirmed = true
      throw error
    }
    await Promise.resolve(handle.done).catch(() => {})
  }

  async run(argv: string[], { cwd, signal, stage }: RuntimeContext & { stage: string }): Promise<string> {
    let handle: ProcessHandle | undefined, result = '', failure: unknown
    try {
      handle = this.spawn(argv, cwd, signal)
      const outcome = await handle.done
      signal.throwIfAborted()
      if (outcome.exitCode !== 0) {
        throw processFailure(stage, `退出码${outcome.exitCode}：${detail(handle.collected?.stderr) || '无错误详情'}`, argv[0], cwd)
      }
      const output = handle.collected?.stdout?.readFrom(0)
      if (typeof output === 'object' && output?.lossy) {
        throw new AmberError('output_truncated', `${stage}阶段的输出超出读取上限；请使用单个视频或更短片段。`)
      }
      result = collectedText(handle.collected?.stdout)
    } catch (error) {
      failure = error instanceof AmberError || signal.aborted ? error
        : processFailure(stage, errorCode(error) || '无法启动或等待进程', argv[0], cwd)
    }
    try { await this.stop(handle) }
    catch (error) { failure = failure ? addCleanup(failure, errorMessage(error), true) : error }
    if (failure) throw failure
    return result
  }

  async encode(ffmpeg: string, gifski: string, source: string, output: string, params: EncodeParams, { cwd, signal }: RuntimeContext): Promise<void> {
    const controller = new AbortController()
    const combined = AbortSignal.any([signal, controller.signal])
    let producer: ProcessHandle | undefined, consumer: ProcessHandle | undefined, failure: unknown, spawning = gifski
    try {
      // The SDK supports collect/pipe/inherit output modes, not output 'ignore'.
      // Keep unused quiet output bounded to one byte rather than forwarding it.
      consumer = this.spawn([gifski, '--quiet', '--quality', params.quality,
        '--motion-quality', params.motion_quality, '--lossy-quality', params.lossy_quality,
        '--fps', params.fps, '--width', params.width, '--height', params.height,
        '--repeat', 0, '--y4m-color-override', 'bt709', '--output', output, '-'], cwd, combined,
      { stdin: 'pipe', stdout: { maxBytes: 1 } })
      spawning = ffmpeg
      producer = this.spawn([ffmpeg, '-hide_banner', '-v', 'error', '-nostdin', '-threads', 2,
        '-ss', params.start, '-t', params.duration_seconds, '-i', source, '-an', '-sn',
        '-vf', `setpts=PTS-STARTPTS,fps=${params.fps},scale=${params.width}:${params.height}:flags=lanczos:out_color_matrix=bt709,setsar=1`,
        '-pix_fmt', 'yuv444p', '-f', 'yuv4mpegpipe', '-'], cwd, combined, { stdout: 'pipe' })
      if (!producer.stdout || !consumer.stdin) throw new AmberError('pipe_unavailable', 'DSH未提供视频管道；请检查subprocess服务版本。')
      const checked = (handle: ProcessHandle, executable: string): Promise<void> => handle.done.then(outcome => {
        if (outcome.exitCode !== 0) throw processFailure('encode',
          `退出码${outcome.exitCode}：${detail(handle.collected?.stderr) || '无错误详情'}`, executable, cwd)
      }, (error: unknown) => { throw processFailure('encode', errorCode(error) || '无法等待进程', executable, cwd) })
      await Promise.all([
        pipeline(producer.stdout, consumer.stdin, { signal: combined }), checked(producer, ffmpeg), checked(consumer, gifski),
      ])
      signal.throwIfAborted()
    } catch (error) {
      failure = signal.aborted ? signal.reason : error
    }
    controller.abort()
    const stopped = await Promise.allSettled([this.stop(producer), this.stop(consumer)])
    if (failure && !(failure instanceof AmberError) && !signal.aborted) {
      // A broken pipe may be observed before the encoder's exit event. Read both
      // bounded diagnostics after shutdown, without blaming the other program.
      const candidates: [ProcessHandle | undefined, string][] = [[consumer, gifski], [producer, ffmpeg]]
      const chosen = candidates.find(([h]) => detail(h?.collected?.stderr)
        && !/broken pipe|pipe has been ended/i.test(detail(h?.collected?.stderr)))
      const [handle, executable] = chosen || [undefined, producer && consumer ? 'FFmpeg + Gifski' : spawning]
      failure = processFailure('encode', detail(handle?.collected?.stderr)
        || errorCode(failure) || '管道中断，未取得可归因的进程诊断', executable, cwd)
    }
    for (const result of stopped) if (result.status === 'rejected') {
      const reason: unknown = result.reason
      failure = failure ? addCleanup(failure, errorMessage(reason), true) : reason
    }
    if (failure) throw failure
  }
}

interface QueueItem {
  resolve(): void
  signal: AbortSignal
  abort(): void
}

export class JobQueue {
  count = 0
  active = false
  waiting: QueueItem[] = []

  constructor(readonly limit = 3) {}

  release(): void {
    this.count--
    const next = this.waiting.shift()
    if (next) { next.signal.removeEventListener('abort', next.abort); next.resolve() }
    else this.active = false
  }

  async run<T>(signal: AbortSignal, body: () => T | Promise<T>): Promise<T> {
    signal.throwIfAborted()
    if (this.count >= this.limit) throw new AmberError('queue_full', '视频任务队列已满，请等待当前任务完成后再试。')
    this.count++
    if (this.active) {
      await new Promise<void>((resolve, reject) => {
        const item: QueueItem = { resolve, signal, abort: () => {
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
