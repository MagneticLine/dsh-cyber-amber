import { constants } from 'node:fs'
import { copyFile, lstat, mkdir, mkdtemp, open, readFile, realpath, rm, stat, unlink } from 'node:fs/promises'
import { basename, dirname, extname, isAbsolute, join, resolve } from 'node:path'
import { randomUUID } from 'node:crypto'
import { AmberError, downloadArgs, fitClip, gifOptions, readConfig, sourceInput } from './options.js'
import { fitBudget } from './budget.js'
import { JobQueue, Runtime } from './runtime.js'

function json(text, stage) {
  try { return JSON.parse(text) } catch { throw new AmberError('invalid_metadata', `${stage}返回的媒体信息无效；请检查依赖版本或换一个视频。`) }
}

function rate(value) {
  const [a, b = '1'] = String(value || '').split('/')
  return Number(a) / Number(b)
}

function safeName(value) {
  return String(value || 'video').replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/, '').slice(0, 55) || 'video'
}

async function removeWork(folder, parent) {
  // Both are plugin-created paths, checked again immediately before recursive deletion.
  const actual = await realpath(folder)
  if (dirname(actual) !== await realpath(parent) || !basename(actual).startsWith('.amber-')
      || (await lstat(folder)).isSymbolicLink()) {
    throw new AmberError('cleanup_path_invalid', '临时目录位置异常，已停止自动清理；请检查输出目录。')
  }
  await rm(actual, { recursive: true, force: true })
}

export class AmberService {
  constructor(ctx, config = {}) {
    this.ctx = ctx
    this.config = readConfig(config)
    this.runtime = new Runtime(ctx.subprocess)
    this.queue = new JobQueue(this.config.maxPending)
    this.shutdown = new AbortController()
    this.jobs = new Set()
  }

  async close() {
    this.shutdown.abort(new Error('plugin unloaded'))
    await Promise.allSettled([...this.jobs])
  }

  async job(args, exec, operation) {
    const timeout = AbortSignal.timeout(this.config.timeoutMs)
    const signal = AbortSignal.any([timeout, this.shutdown.signal, ...(exec.signal ? [exec.signal] : [])])
    const task = this.queue.run(signal, async () => {
      const cwd = exec.agent ? await this.ctx.workingDirectory.ensure(exec.agent, signal) : null
      signal.throwIfAborted()
      const requested = args.output_dir ?? this.config.outputDir
      if (typeof requested !== 'string') throw new AmberError('invalid_output', 'output_dir须为目录路径文本。')
      if ((!requested || !isAbsolute(requested)) && !cwd) {
        throw new AmberError('working_directory_missing', '没有会话工作目录；请提供绝对output_dir，或在配置中填写outputDir。')
      }
      const outputDir = requested ? resolve(cwd || '', requested) : join(cwd, 'cyber-amber')
      await mkdir(outputDir, { recursive: true })
      const root = await realpath(outputDir)
      const work = await mkdtemp(join(root, '.amber-'))
      try { return await operation({ cwd, outputDir: root, work, signal }) }
      finally { await removeWork(work, root) }
    })
    this.jobs.add(task)
    try { return await task }
    catch (error) {
      if (error?.code === 'process_cleanup_failed' || error?.code === 'cleanup_path_invalid') throw error
      if (timeout.aborted) throw new AmberError('timeout', '下载、排队或编码超过总超时；本次进程已停止，请缩短片段或提高timeoutMs后重试。')
      if (signal.aborted) throw new AmberError('cancelled', '本次任务已取消，临时文件已清理，没有自动重试。')
      if (error instanceof AmberError) throw error
      if (['EACCES', 'EPERM'].includes(error?.code)) {
        throw new AmberError('permission_denied', `系统拒绝访问${error.path || '指定文件或目录'}；请检查输出目录及系统防护记录。插件不会自动改权限或更换目录重试。`)
      }
      const code = error?.code || 'unknown'
      throw new AmberError('processing_failed', `文件或媒体处理失败（${code}）；请检查输入路径、输出目录和依赖配置后重试。`)
    } finally { this.jobs.delete(task) }
  }

  async programs(work, signal, gif) {
    const cfg = this.config
    const names = [['ffmpeg', cfg.ffmpegPath], ['ffprobe', cfg.ffprobePath]]
    if (gif) names.push(['gifski', cfg.gifskiPath])
    return Object.fromEntries(await Promise.all(names.map(async ([name, path]) => [name,
      await this.runtime.executable(path, name, signal)])))
  }

  async probe(path, programs, context, gif = false, checkHdr = true) {
    const text = await this.runtime.run([programs.ffprobe, '-v', 'error', ...(gif ? ['-ignore_loop', '1', '-count_frames'] : []),
      '-select_streams', 'v:0', '-show_entries',
      'stream=width,height,avg_frame_rate,r_frame_rate,color_transfer,nb_read_frames:stream_side_data=rotation:format=duration,size',
      '-of', 'json', path], { cwd: context.work, signal: context.signal, stage: 'probe' })
    const value = json(text, 'ffprobe')
    const stream = value.streams?.[0]
    if (!stream) throw new AmberError('no_video', '输入中没有可读取的视频画面，请提供视频文件。')
    let width = Number(stream.width), height = Number(stream.height)
    const rotation = Number(stream.side_data_list?.find(item => item.rotation !== undefined)?.rotation || 0)
    if (Math.abs(rotation) % 180 === 90) [width, height] = [height, width]
    const info = { width, height, fps: rate(stream.avg_frame_rate) || rate(stream.r_frame_rate),
      duration_seconds: Number(value.format?.duration), bytes: Number(value.format?.size),
      frame_count: Number(stream.nb_read_frames) || 0 }
    for (const key of ['width', 'height', 'duration_seconds', 'bytes']) {
      if (!Number.isFinite(info[key]) || info[key] <= 0) throw new AmberError('probe_failed', '媒体尺寸或时长无效；请换一个可正常播放的视频。')
    }
    if (!gif && (!Number.isFinite(info.fps) || info.fps <= 0)) throw new AmberError('probe_failed', '无法确定原视频帧率；请提供正常视频文件。')
    if (!gif && (width * height > 33554432 || Math.max(width, height) > 8192)) {
      throw new AmberError('source_resolution_limit', '原视频分辨率过高；请提供不超过8K的视频。')
    }
    if (!gif && checkHdr && ['smpte2084', 'arib-std-b67'].includes(stream.color_transfer)) {
      throw new AmberError('hdr_unsupported', '当前版本不对HDR做色调映射；请提供SDR版本，避免错误颜色。')
    }
    return info
  }

  async sourceFile(path) {
    let actual
    try { actual = await realpath(path) }
    catch (error) {
      if (error.code === 'ENOENT') throw new AmberError('source_missing', '找不到原视频文件；请确认路径，或重新提供视频链接。')
      throw error
    }
    const value = await stat(actual)
    if (!value.isFile() || !value.size || value.size > this.config.maxSourceMB * 1000000) {
      throw new AmberError('source_size_limit', `原片不是有效文件或超过${this.config.maxSourceMB}MB；请提供更小的视频或调整maxSourceMB。`)
    }
    return actual
  }

  async acquire(url, programs, context, videoOnly) {
    const ytdlp = await this.runtime.executable(this.config.ytdlpPath, 'yt-dlp', context.signal)
    if (this.config.cookiesFile && !(await stat(this.config.cookiesFile)).isFile()) {
      throw new AmberError('cookies_missing', '配置的Cookie文件不存在；请重新导出或清空cookiesFile后重试。')
    }
    const stdout = await this.runtime.run([ytdlp, ...downloadArgs(url, context.work,
      { ...this.config, resolvedFfmpeg: programs.ffmpeg }, videoOnly)],
    { cwd: context.work, signal: context.signal, stage: 'download' })
    const printed = stdout.trim().split(/\r?\n/).filter(Boolean).at(-1)
    if (!printed) throw new AmberError('download_not_created', '下载未产生视频；可能超过大小限制、需要登录或没有可用格式，请检查链接与Cookie配置。')
    const path = await this.sourceFile(resolve(context.work, printed))
    if (dirname(path) !== await realpath(context.work)) {
      throw new AmberError('download_path_invalid', '下载器返回了临时目录以外的文件，已停止处理。')
    }
    let metadata = {}
    try {
      const infoPath = join(context.work, 'media.info.json')
      if ((await stat(infoPath)).size <= 4 * 1024 * 1024) metadata = json(await readFile(infoPath, 'utf8'), 'yt-dlp')
    } catch (error) { if (error instanceof AmberError) throw error }
    return { path, title: String(metadata.title || metadata.id || 'video').slice(0, 300), source: url }
  }

  async publish(source, title, suffix, context) {
    context.signal.throwIfAborted()
    const target = join(context.outputDir, `${safeName(title)}-${randomUUID().slice(0, 12)}${suffix}`)
    try {
      await copyFile(source, target, constants.COPYFILE_EXCL)
      context.signal.throwIfAborted()
      return target
    } catch (error) {
      if (error.code !== 'EEXIST') await unlink(target).catch(() => {})
      throw error
    }
  }

  async download(args, exec = {}) {
    // Validate before queueing, downloading or creating output folders.
    sourceInput(args.url, null, false)
    return this.job(args, exec, async context => {
      const input = sourceInput(args.url, context.cwd, false)
      const programs = await this.programs(context.work, context.signal, false)
      const acquired = await this.acquire(input.value, programs, context, false)
      const info = await this.probe(acquired.path, programs, context, false, false)
      const path = await this.publish(acquired.path, acquired.title, extname(acquired.path), context)
      return { status: 'downloaded', path, title: acquired.title, source: acquired.source, ...info }
    })
  }

  async validateGif(path, params, programs, context) {
    const file = await open(path, 'r')
    try {
      const info = await file.stat()
      const header = Buffer.alloc(Math.min(info.size, 1024)), trailer = Buffer.alloc(1)
      await file.read(header, 0, header.length, 0)
      await file.read(trailer, 0, 1, info.size - 1)
      if (!/^GIF8[79]a/.test(header.toString('ascii', 0, 6)) || trailer[0] !== 0x3b
          || !header.includes(Buffer.from('NETSCAPE2.0\x03\x01\x00\x00\x00', 'binary'))) {
        throw new AmberError('gif_invalid', '输出不是完整的无限循环GIF；请检查Gifski版本。')
      }
    } finally { await file.close() }
    const result = await this.probe(path, programs, context, true)
    if (result.width !== params.width || result.height !== params.height || !result.frame_count
        || result.frame_count > Math.ceil(params.duration_seconds * params.fps) + 1
        || Math.abs(result.duration_seconds - params.duration_seconds) > 2 / params.fps + 0.03) {
      throw new AmberError('gif_invalid', 'GIF的实际画面或时长与片段不一致；请调整起止时间后重试。')
    }
    return { path, width: result.width, height: result.height, bytes: result.bytes,
      frame_count: result.frame_count, duration_seconds: result.duration_seconds,
      fps: params.fps, quality: params.quality, motion_quality: params.motion_quality,
      lossy_quality: params.lossy_quality, start: params.start, end: params.end,
      loop: 0, mode: 'normal' }
  }

  async makeGif(args, exec = {}) {
    const options = gifOptions(args, this.config)
    if (typeof args.source !== 'string' || !args.source.trim()) throw new AmberError('invalid_source', '请提供source链接、BV号或本地视频路径。')
    return this.job(args, exec, async context => {
      const input = sourceInput(args.source, context.cwd)
      const programs = await this.programs(context.work, context.signal, true)
      const acquired = input.kind === 'url' ? await this.acquire(input.value, programs, context, true)
        : { path: await this.sourceFile(input.value), title: basename(input.value, extname(input.value)), source: input.value }
      const info = await this.probe(acquired.path, programs, context)
      const params = fitClip(options, info, this.config.maxClipSeconds)
      let index = 0
      const fitted = await fitBudget(params, async settings => {
        context.signal.throwIfAborted()
        const output = join(context.work, `trial-${index++}.gif`)
        await this.runtime.encode(programs.ffmpeg, programs.gifski, acquired.path, output, settings,
          { cwd: context.work, signal: context.signal })
        return this.validateGif(output, settings, programs, context)
      }, value => unlink(value.path))
      if (fitted.status === 'needs_adjustment') return { ...fitted, source: acquired.source,
        width: params.width, height: params.height, fps: params.fps, start: params.start, end: params.end }
      if (options.guard_bytes && fitted.result.bytes > options.guard_bytes) {
        throw new AmberError('output_size_limit', `GIF实测${fitted.result.bytes}字节，超过配置的${options.guard_bytes}字节保护上限；请调整参数或maxOutputMB后重试。`)
      }
      const path = await this.publish(fitted.result.path, acquired.title, '.gif', context)
      return { ...fitted.result, path, status: 'completed', title: acquired.title,
        source: acquired.source, attempts: fitted.attempts }
    })
  }
}
