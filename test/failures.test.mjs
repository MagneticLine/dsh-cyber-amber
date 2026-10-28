import { test } from 'node:test'
import assert from 'node:assert/strict'
import { PassThrough } from 'node:stream'
import { readdir } from 'node:fs/promises'
import { AmberError } from '../lib/options.js'
import { Runtime } from '../lib/runtime.js'
import { AmberService } from '../lib/service.js'
import { testFolder, removeTestFolder } from './support/fixtures.mjs'

const signal = () => new AbortController().signal
const params = { quality: 75, motion_quality: 75, lossy_quality: 75,
  fps: 20, width: 160, height: 90, start: 0, duration_seconds: 1 }

function handle(exitCode, text, cleanupFails = false) {
  return { done: Promise.resolve({ exitCode }), terminate() {},
    waitForExit: async () => { if (cleanupFails) throw new Error('injected confirmation failure') },
    collected: { stderr: { readFrom: () => ({ text }) } } }
}

test('Gifski and FFmpeg encoder failures identify the actual program', async () => {
  for (const failing of ['gifski.exe', 'ffmpeg.exe']) {
    const runtime = new Runtime({ spawn(spec) {
      const isConsumer = spec.argv[0] === 'gifski.exe'
      const h = handle(spec.argv[0] === failing ? 13 : 0,
        spec.argv[0] === failing ? 'Permission denied' : '')
      if (isConsumer) h.stdin = new PassThrough()
      else { h.stdout = new PassThrough(); h.stdout.end('frame') }
      return h
    } })
    await assert.rejects(runtime.encode('ffmpeg.exe', 'gifski.exe', 'input', 'output', params,
      { cwd: '.', signal: signal() }), error => error.code === 'permission_denied'
        && error.message.startsWith(`[permission_denied] ${failing}`))
  }
})

test('run preserves the original error when exit confirmation also fails', async () => {
  const runtime = new Runtime({ spawn: () => handle(9, 'original failure', true) })
  await assert.rejects(runtime.run(['yt-dlp.exe'], { cwd: '.', signal: signal(), stage: 'download' }),
    error => error.code === 'download_failed' && error.message.includes('original failure')
      && error.message.includes('未能确认') && error.processesUnconfirmed)
})

test('synchronous spawn refusal is attributed without retrying', async () => {
  let calls = 0
  const runtime = new Runtime({ spawn() { calls++; throw Object.assign(new Error('injected'), { code: 'EACCES' }) } })
  await assert.rejects(runtime.run(['ffprobe.exe'], { cwd: '.', signal: signal(), stage: 'probe' }),
    error => error.code === 'permission_denied' && error.message.includes('ffprobe.exe'))
  assert.equal(calls, 1)
})

test('abort reasons with read-only DOMException messages preserve cleanup diagnostics', async () => {
  const ctl = new AbortController()
  const runtime = new Runtime({ spawn() {
    ctl.abort()
    return handle(0, '', true)
  } })
  await assert.rejects(runtime.run(['ffmpeg.exe'], { cwd: '.', signal: ctl.signal, stage: 'encode' }),
    error => error.name === 'AbortError' && error.processesUnconfirmed && error.message.includes('未能确认'))
})

test('failed exit observation does not wait forever for an unresolved done promise', async () => {
  const runtime = new Runtime({})
  await assert.rejects(runtime.stop({ terminate() {}, done: new Promise(() => {}),
    waitForExit: async () => { throw new Error('injected') } }), /process_cleanup_failed/)
})

test('bounded process diagnostics omit URL queries and authorization contents', async () => {
  const runtime = new Runtime({ spawn: () => handle(1,
    'request https://example.com/a?token=secret\nAuthorization: Bearer hidden-token\nCookie: SESSDATA=hidden-cookie\noriginal failure') })
  await assert.rejects(runtime.run(['yt-dlp.exe'], { cwd: '.', signal: signal(), stage: 'download' }),
    error => error.message.includes('original failure') && !/secret|hidden-token|hidden-cookie/.test(error.message))
})

test('processing errors survive directory cleanup errors; successful results carry warnings', async () => {
  const root = await testFolder('cleanup-')
  const service = new AmberService({ subprocess: {}, workingDirectory: {} }, { outputDir: root })
  service.cleanup = async () => { throw Object.assign(new Error('injected cleanup refusal'), { code: 'EPERM' }) }
  try {
    await assert.rejects(service.job({}, {}, async () => { throw new AmberError('probe_failed', 'original probe error') }),
      error => error.code === 'probe_failed' && error.message.includes('original probe error')
        && error.message.includes('EPERM') && error.message.includes(root))
    const result = await service.job({}, {}, async () => ({ status: 'completed', path: 'retained.gif' }))
    assert.equal(result.path, 'retained.gif')
    assert.equal(result.warnings.length, 1)
    assert(result.warnings[0].includes(root))
  } finally { await service.close(); await removeTestFolder(root) }
})

test('unconfirmed processes prevent recursive deletion and retain the original failure', async () => {
  const root = await testFolder('unconfirmed-')
  const service = new AmberService({ subprocess: {}, workingDirectory: {} }, { outputDir: root })
  let cleaned = false
  service.cleanup = async () => { cleaned = true }
  try {
    await assert.rejects(service.job({}, {}, async () => {
      throw Object.assign(new AmberError('encode_failed', 'original encoder failure'), { processesUnconfirmed: true })
    }), error => error.code === 'encode_failed' && error.message.includes('未自动删除') && error.message.includes(root))
    assert.equal(cleaned, false)
    assert.equal((await readdir(root)).filter(name => name.startsWith('.amber-')).length, 1)
    assert.equal(service.queue.count, 0)
  } finally { await service.close(); await removeTestFolder(root) }
})

test('cancellation retains secondary cleanup failure and does not claim cleanup succeeded', async () => {
  const root = await testFolder('cancel-cleanup-'), ctl = new AbortController()
  const service = new AmberService({ subprocess: {}, workingDirectory: {} }, { outputDir: root })
  service.cleanup = async () => { throw Object.assign(new Error('injected'), { code: 'EPERM' }) }
  try {
    await assert.rejects(service.job({}, { signal: ctl.signal }, async () => {
      ctl.abort(); throw ctl.signal.reason
    }), error => error.code === 'cancelled' && error.message.includes('清理失败')
      && !error.message.includes('已清理'))
  } finally { await service.close(); await removeTestFolder(root) }
})
