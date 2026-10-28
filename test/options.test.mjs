import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { DEFAULTS, readConfig, timecode, gifOptions, fitClip, sourceInput, downloadArgs } from '../lib/options.js'

test('default settings and quality coupling are explicit', () => {
  const p = gifOptions({}, readConfig())
  assert.deepEqual([p.long_edge, p.fps, p.quality, p.motion_quality, p.lossy_quality], [640, 20, 75, 75, 75])
  assert.equal(p.max_bytes, 0)
  assert.equal(gifOptions({ quality: 40 }, DEFAULTS).min_quality, 40)
  assert.equal(gifOptions({ quality: 80 }, DEFAULTS).lossy_quality, 80)
  assert.equal(gifOptions({ max_size_mb: 3 }, DEFAULTS).max_bytes, 3000000)
})

test('seconds, decimals and mixed Chinese colons have identical meaning', () => {
  for (const t of [2, '2', '2.0', '00:02', '00：02', '00：00:02']) assert.equal(timecode(t), 2)
  assert.equal(timecode('-00：02'), -2)
  assert.equal(timecode('01:02:03.5'), 3723.5)
  for (const t of ['00:61', '1.5:02', '', 'x', '1:2:3:4', Infinity, NaN]) assert.throws(() => timecode(t))
})

test('bounds fit the source without upscaling or duplicating source FPS', () => {
  const p = fitClip(gifOptions({ start: -2, end: 20 }, DEFAULTS),
    { duration_seconds: 6, width: 301, height: 181, fps: 8 }, 30)
  assert.deepEqual([p.start, p.end, p.width, p.height, p.fps], [0, 6, 301, 181, 8])
  const small = fitClip(gifOptions({}, DEFAULTS), { duration_seconds: 3, width: 1000, height: 625, fps: 30 }, 30)
  assert.deepEqual([small.width, small.height], [640, 400])
})

test('empty, reversed and overly long clips are rejected without implicit shortening', () => {
  assert.throws(() => gifOptions({ start: 3, end: 2 }, DEFAULTS), /invalid_range/)
  const info = { duration_seconds: 60, width: 640, height: 400, fps: 20 }
  assert.throws(() => fitClip(gifOptions({}, DEFAULTS), info, 30), /clip_too_long/)
  assert.throws(() => fitClip(gifOptions({ start: 60 }, DEFAULTS), info, 30), /empty_range/)
})

test('invalid numeric settings are rejected instead of silently clamped', () => {
  for (const args of [{ fps: 31 }, { quality: 0 }, { long_edge: 127 }, { motion_quality: 101 },
    { lossy_quality: NaN }, { max_size_mb: 0 }, { fps: 2.5 }, { quality: '75' }]) {
    assert.throws(() => gifOptions(args, DEFAULTS))
  }
  assert.throws(() => readConfig({ maxPending: 0 }))
  assert.throws(() => readConfig({ cookiesFile: 'relative.txt' }))
})

test('BV numbers, share links and Unicode local paths are distinct source kinds', () => {
  assert.equal(sourceInput('BV1RwnQ6sEd5', null).value, 'https://www.bilibili.com/video/BV1RwnQ6sEd5')
  assert.equal(sourceInput('https://b23.tv/example', null).kind, 'url')
  assert.equal(sourceInput('中文 video.mp4', process.cwd()).value, resolve('中文 video.mp4'))
  assert.throws(() => sourceInput('file:///tmp/file', null))
  assert.throws(() => sourceInput('local.mp4', null, false))
  assert.throws(() => sourceInput('https://user:password@example.com', null))
})

test('download argv is config-isolated, single-video and keeps URL as one argument', () => {
  const url = 'https://www.bilibili.com/video/BV1RwnQ6sEd5/?x=a&y=b'
  const args = downloadArgs(url, resolve('.'), DEFAULTS, true)
  assert.equal(args.at(-1), url)
  assert.equal(args.at(-2), '--')
  assert(args.includes('--ignore-config'))
  assert(args.includes('--no-playlist'))
  assert.equal(args[args.indexOf('-f') + 1], 'bv[height<=1080]/b[height<=1080]')
  assert(!args.includes('--merge-output-format'))
  const audio = downloadArgs(url, resolve('.'), { ...DEFAULTS, cookiesFile: 'cookie path', proxy: 'http://127.0.0.1:7897' }, false)
  assert(audio[audio.indexOf('-f') + 1].includes('+ba'))
  assert.equal(audio[audio.indexOf('--cookies') + 1], 'cookie path')
})
