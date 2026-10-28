import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { access, mkdtemp, readFile, readdir, rm, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { AmberService } from '../lib/service.js'
import { JobQueue, Runtime, collectedText } from '../lib/runtime.js'
import { nativeRuntime } from './support/native-runtime.mjs'

let root, source, originalHash, programs
const hash = bytes => createHash('sha256').update(bytes).digest('hex')

before(async () => {
  root = await mkdtemp(join(tmpdir(), 'amber-tests-'))
  source = join(root, '原片 video with spaces.mp4')
  const subprocess = nativeRuntime(), runtime = new Runtime(subprocess)
  const signal = AbortSignal.timeout(30000)
  programs = { ffmpegPath: await runtime.executable(process.env.AMBER_TEST_FFMPEG, 'ffmpeg', signal),
    ffprobePath: await runtime.executable(process.env.AMBER_TEST_FFPROBE, 'ffprobe', signal),
    gifskiPath: await runtime.executable(process.env.AMBER_TEST_GIFSKI, 'gifski', signal) }
  await runtime.run([programs.ffmpegPath, '-v', 'error', '-f', 'lavfi', '-i',
    'testsrc2=size=320x180:rate=20:duration=3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', source],
  { cwd: root, signal, stage: 'fixture' })
  originalHash = hash(await readFile(source))
})

after(async () => { if (root) await rm(root, { recursive: true, force: true }) })

function setup(name, extra = {}, subprocess = nativeRuntime()) {
  const outputDir = join(root, name)
  const ctx = { subprocess, workingDirectory: { ensure: async () => root } }
  const service = new AmberService(ctx, { ...programs, outputDir, ...extra })
  return { service, subprocess, outputDir }
}

async function cleanState(state) {
  await state.service.close()
  assert.equal(state.subprocess.live.size, 0)
  assert.equal(state.service.queue.count, 0)
  const names = await readdir(state.outputDir).catch(() => [])
  assert(!names.some(n => n.startsWith('.amber-')))
  assert.equal(hash(await readFile(source)), originalHash)
}

test('real default encoding passes Q75 M75 L75 to Gifski and preserves source', async () => {
  const s = setup('default')
  try {
    const out = await s.service.makeGif({ source, start: 0, end: 1 })
    assert.equal(out.status, 'completed')
    assert.deepEqual([out.quality, out.motion_quality, out.lossy_quality, out.fps], [75, 75, 75, 20])
    assert.deepEqual([out.width, out.height, out.frame_count], [320, 180, 20])
    assert.equal(out.duration_seconds, 1)
    assert.equal(out.bytes, (await stat(out.path)).size)
    const command = s.subprocess.seen.find(x => x.argv[0] === programs.gifskiPath).argv
    for (const option of ['--quality', '--motion-quality', '--lossy-quality']) assert.equal(command[command.indexOf(option) + 1], '75')
    assert(!command.includes('--extra'))
    assert.equal(out.attempts.length, 1)
  } finally { await cleanState(s) }
})

test('Chinese times clamp to source bounds and manual settings are retained', async () => {
  const s = setup('manual')
  try {
    const out = await s.service.makeGif({ source, start: '-00：01', end: '00：04',
      long_edge: 160, fps: 10, quality: 80, motion_quality: 60, lossy_quality: 100 })
    assert.deepEqual([out.start, out.end, out.width, out.height, out.fps], [0, 3, 160, 90, 10])
    assert.deepEqual([out.quality, out.motion_quality, out.lossy_quality], [80, 60, 100])
    assert.equal(out.frame_count, 30)
    assert.equal(out.duration_seconds, 3)
  } finally { await cleanState(s) }
})

test('real over-budget request returns advice, does not silently resize and cleans all trial GIFs', async () => {
  const s = setup('budget')
  try {
    const out = await s.service.makeGif({ source, end: 1, max_size_mb: 0.000001 })
    assert.equal(out.status, 'needs_adjustment')
    assert.equal(out.limit_bytes, 1)
    assert.deepEqual(out.attempts.map(x => x.quality), [75, 50])
    assert.equal(out.width, 320)
    assert.equal(out.suggestions.length, 3)
    assert.equal(out.path, undefined)
    assert.deepEqual(await readdir(s.outputDir), [])
  } finally { await cleanState(s) }
})

test('no automatic retry for independent Q/L and explicit size guard', async () => {
  const s = setup('guard', { maxOutputMB: 0.000001 })
  try {
    await assert.rejects(s.service.makeGif({ source, end: 1, quality: 60, lossy_quality: 100 }), /output_size_limit/)
    assert.equal(s.subprocess.seen.filter(x => x.argv[0] === programs.gifskiPath).length, 1)
    assert.deepEqual(await readdir(s.outputDir), [])
  } finally { await cleanState(s) }
})

test('video download entry preserves media; GIF URL entry reuses one download for all trials', async () => {
  const native = nativeRuntime()
  const spawn = native.spawn.bind(native)
  const fixture = fileURLToPath(new URL('./support/fixture-downloader.mjs', import.meta.url))
  native.spawn = spec => spawn(spec.argv[0] === process.execPath && spec.argv.includes('--ignore-config')
    ? { ...spec, argv: [process.execPath, fixture, source, ...spec.argv.slice(1)] } : spec)
  const s = setup('download', { ytdlpPath: process.execPath }, native)
  try {
    const out = await s.service.download({ url: 'BV1RwnQ6sEd5' })
    assert.equal(out.status, 'downloaded')
    assert.equal(hash(await readFile(out.path)), originalHash)
    const downloadsBefore = native.seen.filter(x => x.argv.includes('--ignore-config')).length
    const gif = await s.service.makeGif({ source: 'BV1RwnQ6sEd5', end: 1, max_size_mb: 0.000001 })
    assert.equal(gif.status, 'needs_adjustment')
    assert.equal(native.seen.filter(x => x.argv.includes('--ignore-config')).length - downloadsBefore, 1)
    assert.equal(hash(await readFile(out.path)), originalHash)
    const inputFormats = native.seen.filter(x => x.argv.includes('--ignore-config')).map(x => x.argv[x.argv.indexOf('-f') + 1])
    assert(inputFormats[0].includes('+ba'))
    assert(!inputFormats[1].includes('+ba'))
  } finally { await cleanState(s) }
})

test('missing downloader and failed media probe give actionable errors and remove work folders', async () => {
  const s = setup('missing', { ytdlpPath: 'amber-test-no-ytdlp' })
  try {
    await assert.rejects(s.service.download({ url: 'BV1RwnQ6sEd5' }), /runtime_missing.*yt-dlp.*ytdlpPath/)
    await assert.rejects(s.service.makeGif({ source: join(root, 'missing.mp4') }), /source_missing/)
    assert.deepEqual(await readdir(s.outputDir), [])
  } finally { await cleanState(s) }
})

test('invalid or empty ranges do not start encoders or leave temporary files', async () => {
  const s = setup('invalid')
  try {
    await assert.rejects(s.service.makeGif({ source, start: 6, end: 8 }), /empty_range/)
    await assert.rejects(s.service.makeGif({ source, quality: 0 }), /invalid_parameter/)
    assert(!s.subprocess.seen.some(x => x.argv[0] === programs.gifskiPath))
  } finally { await cleanState(s) }
})

test('actual runtime observes cancellation and collects structured DSH reader output', async () => {
  const native = nativeRuntime(), runtime = new Runtime(native)
  const ctl = new AbortController()
  const promise = runtime.run([process.execPath, '-e', 'setTimeout(()=>{},60000)'],
    { cwd: root, signal: ctl.signal, stage: 'fixture' })
  setTimeout(() => ctl.abort(new Error('cancel test')), 80)
  await assert.rejects(promise, /cancel test/)
  assert.equal(native.live.size, 0)
  assert.equal(collectedText({ readFrom: () => ({ text: 'value', nextOffset: 5, lossy: false }) }), 'value')
})

test('service timeout and caller cancellation stop a running child and clean work folders', async () => {
  for (const kind of ['timeout', 'cancel']) {
    const s = setup(kind, { timeoutMs: kind === 'timeout' ? 1000 : 10000 })
    const ctl = new AbortController()
    let started
    const ready = new Promise(resolve => { started = resolve })
    s.service.runtime.encode = async (...args) => {
      const context = args.at(-1)
      started()
      return s.service.runtime.run([process.execPath, '-e', 'setTimeout(()=>{},60000)'],
        { ...context, stage: 'encode' })
    }
    try {
      const promise = s.service.makeGif({ source, end: 1 }, { signal: ctl.signal })
      promise.catch(() => {})
      await ready
      if (kind === 'cancel') setTimeout(() => ctl.abort(), 80)
      await assert.rejects(promise, kind === 'timeout' ? /\[timeout\]/ : /\[cancelled\]/)
    } finally { await cleanState(s) }
  }
})

test('queue is serial, bounded, and frees a cancelled waiter immediately', async () => {
  const queue = new JobQueue(3), ctl = new AbortController()
  let release
  const held = queue.run(new AbortController().signal, () => new Promise(resolve => { release = resolve }))
  const pending = queue.run(ctl.signal, () => assert.fail('cancelled waiter ran'))
  pending.catch(() => {})
  const next = queue.run(new AbortController().signal, () => 'next')
  await assert.rejects(queue.run(new AbortController().signal, () => {}), /queue_full/)
  ctl.abort(new Error('wait cancelled'))
  await assert.rejects(pending, /wait cancelled/)
  assert.equal(queue.count, 2)
  release('done')
  assert.equal(await held, 'done')
  assert.equal(await next, 'next')
  assert.equal(queue.count, 0)
})

test('missing session requires explicit output dir and default output follows workingDirectory', async () => {
  const s = setup('workdir', { outputDir: '' })
  try {
    await assert.rejects(s.service.makeGif({ source, end: 1 }), /working_directory_missing/)
    const out = await s.service.makeGif({ source, end: 0.5 }, { agent: {} })
    assert.equal(resolve(out.path, '..'), join(root, 'cyber-amber'))
  } finally { await cleanState(s) }
})
