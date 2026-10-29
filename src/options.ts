import { isAbsolute, resolve } from 'node:path'

export interface AmberConfig {
  outputDir: string; ffmpegPath: string; ffprobePath: string; gifskiPath: string; ytdlpPath: string
  cookiesFile: string; proxy: string; sourceHeight: number; longEdge: number; fps: number
  quality: number; motionQuality: number; maxClipSeconds: number; timeoutMs: number
  maxPending: number; maxSourceMB: number; maxOutputMB: number
}
export interface ConfigField { description: string; min?: number; max?: number; integer?: boolean }
export interface GifArguments {
  source?: unknown; url?: unknown; output_dir?: unknown; quality?: unknown; lossy_quality?: unknown
  motion_quality?: unknown; min_quality?: unknown; start?: unknown; end?: unknown
  max_size_mb?: unknown; long_edge?: unknown; fps?: unknown
}
export interface GifOptions {
  start: number; end: number | null; quality: number; lossy_quality: number; motion_quality: number
  long_edge: number; fps: number; min_quality: number; max_bytes: number; guard_bytes: number
}
export interface ClipInfo { duration_seconds: number; width: number; height: number; fps: number }
export interface ClipOptions extends GifOptions { end: number; width: number; height: number; duration_seconds: number }
export interface CleanupError extends Error { code?: unknown; cleanupNotes?: string[]; processesUnconfirmed?: boolean }

/** Read only known properties after narrowing an untrusted error/object. */
export function record(value: unknown): Record<string, unknown> {
  return value !== null && (typeof value === 'object' || typeof value === 'function')
    ? value as Record<string, unknown> : {}
}
export function errorCode(error: unknown): unknown { return record(error).code }
export function cleanupNotes(error: unknown): string[] {
  const notes = record(error).cleanupNotes
  return Array.isArray(notes) ? notes.filter((note): note is string => typeof note === 'string') : []
}

export class AmberError extends Error {
  code: string
  cleanupNotes?: string[]
  processesUnconfirmed?: boolean
  constructor(code: string, message: string) {
    super(`[${code}] ${message}`)
    this.name = 'AmberError'
    this.code = code
  }
}

export const DEFAULTS: Readonly<AmberConfig> = Object.freeze({
  outputDir: '', ffmpegPath: '', ffprobePath: '', gifskiPath: '', ytdlpPath: '',
  cookiesFile: '', proxy: '', sourceHeight: 1080, longEdge: 640, fps: 20,
  quality: 75, motionQuality: 75, maxClipSeconds: 30, timeoutMs: 300000,
  maxPending: 3, maxSourceMB: 512, maxOutputMB: 0,
})

// One contract for the host settings page and direct/programmatic callers.
export const CONFIG_FIELDS: Readonly<Record<keyof AmberConfig, ConfigField>> = Object.freeze({
  outputDir: { description: '输出目录；留空使用会话工作目录下 cyber-amber。' },
  ffmpegPath: { description: 'FFmpeg 覆盖路径；留空使用包内固定版本。' },
  ffprobePath: { description: 'ffprobe 覆盖路径；留空使用包内固定版本。' },
  gifskiPath: { description: 'Gifski 覆盖路径；留空使用包内固定版本。' },
  ytdlpPath: { description: 'yt-dlp 覆盖路径；留空使用包内固定版本。' },
  cookiesFile: { description: 'Netscape Cookie 文件绝对路径；留空不提供登录凭据。' },
  proxy: { description: '下载代理地址；留空不额外指定代理，不会修改系统代理。' },
  sourceHeight: { min: 144, max: 2160, integer: true, description: '下载格式高度上限；未知分辨率的流在下载后报告实际尺寸。' },
  longEdge: { min: 128, max: 1920, integer: true, description: 'GIF 最长边像素数，等比缩放，不放大显示画面。' },
  fps: { min: 1, max: 30, integer: true, description: 'GIF 采样帧率，不超过原片平均帧率。' },
  quality: { min: 1, max: 100, integer: true, description: 'Gifski 默认 Q；L 默认跟随 Q。' },
  motionQuality: { min: 1, max: 100, integer: true, description: 'Gifski 默认 M，独立于 Q/L，不是帧率百分比。' },
  maxClipSeconds: { min: 1, max: 120, description: '单次片段最长秒数；超长需要选择片段，不自动截短。' },
  timeoutMs: { min: 1000, max: 1800000, integer: true, description: '总超时毫秒数，包含排队、下载、探测及所有编码尝试。' },
  maxPending: { min: 1, max: 8, integer: true, description: '任务总数上限，包含一个执行任务；默认 3 表示最多再排队两个。' },
  maxSourceMB: { min: 1, max: 4096, description: '原片大小限制，1MB=1000000 字节；不是任务峰值磁盘配额。' },
  maxOutputMB: { min: 0, max: 4096, description: '成品 GIF 保护上限，0 表示关闭；超限报错，不自动降质，不是临时磁盘配额。' },
})

export function number(value: unknown, name: string, min: number, max: number, integer = false): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max
      || integer && !Number.isInteger(value)) {
    throw new AmberError('invalid_parameter', `${name}须为${min}至${max}的${integer ? '整数' : '数值'}，请修改后重试。`)
  }
  return value
}

export function readConfig(raw: unknown = {}): Readonly<AmberConfig> {
  const cfg: Record<string, unknown> = { ...DEFAULTS, ...record(raw) }
  for (const name of ['outputDir', 'ffmpegPath', 'ffprobePath', 'gifskiPath', 'ytdlpPath', 'cookiesFile', 'proxy']) {
    if (typeof cfg[name] !== 'string') throw new AmberError('invalid_config', `${name}须为文本。`)
    cfg[name] = cfg[name].trim()
  }
  for (const [name, field] of Object.entries(CONFIG_FIELDS)) {
    if (field.min !== undefined && field.max !== undefined) number(cfg[name], name, field.min, field.max, field.integer)
  }
  if (typeof cfg.cookiesFile === 'string' && cfg.cookiesFile && !isAbsolute(cfg.cookiesFile)) {
    throw new AmberError('invalid_config', 'cookiesFile须为绝对路径；使用导出的Netscape格式Cookie文件。')
  }
  // Every declared field above has now been validated against the shared contract.
  return Object.freeze(cfg) as Readonly<AmberConfig>
}

/** Display provenance only. Never use this lossy value to request the media. */
export function displaySource(value: string): string {
  if (!/^https?:\/\//i.test(value)) return value
  const url = new URL(value)
  url.username = ''; url.password = ''; url.hash = ''
  const allowed = new URLSearchParams()
  const host = url.hostname.toLowerCase()
  if (host === 'youtube.com' || host.endsWith('.youtube.com')) {
    const v = url.searchParams.get('v')
    if (v && /^[\w-]{1,64}$/.test(v)) allowed.set('v', v)
  }
  if (host === 'bilibili.com' || host.endsWith('.bilibili.com')) {
    const p = url.searchParams.get('p')
    if (p && /^\d{1,6}$/.test(p)) allowed.set('p', p)
  }
  url.search = allowed.toString()
  return url.href
}

export function addCleanup(error: unknown, message: string, unconfirmed = false): CleanupError {
  let result: CleanupError
  if (!(error instanceof AmberError)) {
    const original = record(error)
    result = new Error(typeof original.message === 'string' && original.message || '处理已中止', { cause: error })
    result.name = typeof original.name === 'string' && original.name || 'Error'
    result.code = original.code
    result.cleanupNotes = cleanupNotes(error)
    result.processesUnconfirmed = original.processesUnconfirmed === true
  } else result = error
  result.cleanupNotes = [...(result.cleanupNotes || []), message]
  result.message += `；${message}`
  if (unconfirmed) result.processesUnconfirmed = true
  return result
}

export function timecode(value: unknown, name = '时间'): number {
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

export function sourceInput(value: unknown, cwd: string | null | undefined, localAllowed = true): { kind: 'url' | 'local'; value: string } {
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

export function gifOptions(args: GifArguments, cfg: Readonly<AmberConfig>): GifOptions {
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

export function fitClip(options: GifOptions, info: ClipInfo, maxSeconds: number): ClipOptions {
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

export function downloadArgs(url: string, folder: string, cfg: Readonly<AmberConfig> & { resolvedFfmpeg?: string }, videoOnly: boolean): string[] {
  const video = `bv[height<=?${cfg.sourceHeight}]`
  const combined = `b[height<=?${cfg.sourceHeight}]`
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
