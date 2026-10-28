import { isAbsolute, resolve } from 'node:path'

export class AmberError extends Error {
  constructor(code, message) {
    super(`[${code}] ${message}`)
    this.name = 'AmberError'
    this.code = code
  }
}

export const DEFAULTS = Object.freeze({
  outputDir: '', ffmpegPath: '', ffprobePath: '', gifskiPath: '', ytdlpPath: '',
  cookiesFile: '', proxy: '', sourceHeight: 1080, longEdge: 640, fps: 20,
  quality: 75, motionQuality: 75, maxClipSeconds: 30, timeoutMs: 300000,
  maxPending: 3, maxSourceMB: 512, maxOutputMB: 0,
})

export function number(value, name, min, max, integer = false) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max
      || integer && !Number.isInteger(value)) {
    throw new AmberError('invalid_parameter', `${name}须为${min}至${max}的${integer ? '整数' : '数值'}，请修改后重试。`)
  }
  return value
}

export function readConfig(raw = {}) {
  const cfg = { ...DEFAULTS, ...raw }
  for (const name of ['outputDir', 'ffmpegPath', 'ffprobePath', 'gifskiPath', 'ytdlpPath', 'cookiesFile', 'proxy']) {
    if (typeof cfg[name] !== 'string') throw new AmberError('invalid_config', `${name}须为文本。`)
    cfg[name] = cfg[name].trim()
  }
  for (const [name, min, max, integer] of [
    ['sourceHeight', 144, 2160, true], ['longEdge', 128, 1920, true], ['fps', 1, 30, true],
    ['quality', 1, 100, true], ['motionQuality', 1, 100, true], ['maxClipSeconds', 1, 120],
    ['timeoutMs', 1000, 1800000, true], ['maxPending', 1, 8, true], ['maxSourceMB', 1, 4096],
    ['maxOutputMB', 0, 4096],
  ]) number(cfg[name], name, min, max, integer)
  if (cfg.cookiesFile && !isAbsolute(cfg.cookiesFile)) {
    throw new AmberError('invalid_config', 'cookiesFile须为绝对路径；使用导出的Netscape格式Cookie文件。')
  }
  return Object.freeze(cfg)
}

export function timecode(value, name = '时间') {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value !== 'string') throw new AmberError('invalid_time', `${name}请使用秒、分:秒或时:分:秒。`)
  const text = value.trim().replaceAll('：', ':')
  const sign = text.startsWith('-') ? -1 : 1
  const parts = text.replace(/^-/, '').split(':')
  if (parts.length > 3 || !parts.every(p => /^\d+(?:\.\d+)?$/.test(p))
      || parts.length > 1 && (parts.slice(0, -1).some(p => p.includes('.'))
        || parts.slice(1).some(p => Number(p) >= 60))) {
    throw new AmberError('invalid_time', `${name}格式无效；例：2、2.5、00：02、01:02:03。`)
  }
  const seconds = parts.reduce((total, part) => total * 60 + Number(part), 0) * sign
  if (!Number.isFinite(seconds)) throw new AmberError('invalid_time', `${name}超出有效数值范围。`)
  return seconds
}

export function sourceInput(value, cwd, localAllowed = true) {
  if (typeof value !== 'string' || !value.trim() || value.length > 8192 || value.includes('\0')) {
    throw new AmberError('invalid_source', '请提供一个视频链接、BV号或本地视频路径。')
  }
  const input = value.trim()
  const bv = /^BV[A-Za-z0-9]{10}$/.test(input)
  const av = /^av\d+$/i.test(input)
  if (bv || av) return { kind: 'url', value: `https://www.bilibili.com/video/${input}` }
  if (/^https?:\/\//i.test(input)) {
    let url
    try { url = new URL(input) }
    catch { throw new AmberError('invalid_source', '视频链接格式无效；请提供完整的HTTP(S)页面链接。') }
    if (url.username || url.password) throw new AmberError('invalid_source', '链接不能内嵌账号密码；请在配置中指定Cookie文件。')
    return { kind: 'url', value: url.href }
  }
  if (!localAllowed || /^[a-z][a-z\d+.-]*:\/\//i.test(input)) {
    throw new AmberError('invalid_source', '下载入口需要HTTP(S)视频页面链接或BV号；本地视频请交给amber_make_gif。')
  }
  if (!isAbsolute(input) && !cwd) throw new AmberError('working_directory_missing', '相对路径需要会话工作目录；请提供绝对路径。')
  return { kind: 'local', value: resolve(cwd || '', input) }
}

export function gifOptions(args, cfg) {
  const quality = number(args.quality ?? cfg.quality, 'quality', 1, 100, true)
  const lossy = number(args.lossy_quality ?? quality, 'lossy_quality', 1, 100, true)
  const floor = Math.min(quality, number(args.min_quality ?? 50, 'min_quality', 1, 100, true))
  const start = timecode(args.start ?? 0, 'start')
  const end = args.end === undefined ? null : timecode(args.end, 'end')
  if (end !== null && end <= start) throw new AmberError('invalid_range', '结束时间须大于开始时间，请调整起止时间。')
  const limit = args.max_size_mb === undefined ? 0 : number(args.max_size_mb, 'max_size_mb', 0.000001, 4096)
  const guard = cfg.maxOutputMB
  return {
    start, end, quality, lossy_quality: lossy,
    motion_quality: number(args.motion_quality ?? cfg.motionQuality, 'motion_quality', 1, 100, true),
    long_edge: number(args.long_edge ?? cfg.longEdge, 'long_edge', 128, 1920, true),
    fps: number(args.fps ?? cfg.fps, 'fps', 1, 30, true),
    min_quality: floor,
    max_bytes: limit ? Math.floor(limit * 1000000) : 0,
    guard_bytes: guard ? Math.floor(guard * 1000000) : 0,
  }
}

export function fitClip(options, info, maxSeconds) {
  const start = Math.max(0, Math.min(options.start, info.duration_seconds))
  const end = Math.max(0, Math.min(options.end ?? info.duration_seconds, info.duration_seconds))
  if (end <= start) throw new AmberError('empty_range', '所选时间段没有可用画面，请换一个片段。')
  if (end - start > maxSeconds) {
    throw new AmberError('clip_too_long', `所选片段为${(end - start).toFixed(2)}秒，超过${maxSeconds}秒上限；请指定更短的起止时间。`)
  }
  const ratio = Math.min(1, options.long_edge / Math.max(info.width, info.height))
  // Floor instead of rounding up: never enlarge a small source or exceed the requested edge.
  const width = Math.max(1, Math.floor(info.width * ratio))
  const height = Math.max(1, Math.floor(info.height * ratio))
  const fps = Math.min(options.fps, info.fps)
  const duration = end - start
  if (width * height * fps * duration > 350000000) {
    throw new AmberError('work_limit', '这组时长、尺寸和帧率的计算量过大；请缩短片段或降低尺寸、帧率。')
  }
  return { ...options, start, end, width, height, fps, duration_seconds: duration }
}

export function downloadArgs(url, folder, cfg, videoOnly) {
  const video = `bv[height<=${cfg.sourceHeight}]`
  const combined = `b[height<=${cfg.sourceHeight}]`
  const args = ['--ignore-config', '--no-playlist', '--no-progress', '--no-simulate',
    '--retries', '1', '--fragment-retries', '1', '--socket-timeout', '30',
    '--max-filesize', String(Math.floor(cfg.maxSourceMB * 1000000)),
    '--no-write-thumbnail', '--no-write-subs', '--no-write-auto-subs',
    '-f', videoOnly ? `${video}/${combined}` : `${video}+ba/${combined}/${video}`,
    '--ffmpeg-location', cfg.resolvedFfmpeg || cfg.ffmpegPath || 'ffmpeg',
    '-P', folder, '-o', 'media.%(ext)s', '--write-info-json', '--no-clean-info-json',
    '--print', 'after_move:filepath']
  if (!videoOnly) args.push('--merge-output-format', 'mkv')
  if (cfg.cookiesFile) args.push('--cookies', cfg.cookiesFile)
  if (cfg.proxy) args.push('--proxy', cfg.proxy)
  args.push('--', url)
  return args
}
