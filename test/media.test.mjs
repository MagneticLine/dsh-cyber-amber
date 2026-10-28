import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import { join } from 'node:path'
import { AmberService } from '../lib/service.js'
import { nativeRuntime } from './support/native-runtime.mjs'
import { testFolder, removeTestFolder, writeVideo } from './support/fixtures.mjs'

let root, source, service, programs, runtime
before(async () => {
  root = await testFolder('media-boundaries-')
  source = join(root, 'source.avi')
  await writeVideo(source)
  runtime = nativeRuntime()
  service = new AmberService({ subprocess: runtime, workingDirectory: {} }, { outputDir: root })
  programs = await service.programs(root, AbortSignal.timeout(30000), true)
})
after(async () => { await service?.close(); assert.equal(runtime?.live.size, 0); if (root) await removeTestFolder(root) })

async function variant(name, options, extraInputs = []) {
  const output = join(root, name)
  await service.runtime.run([programs.ffmpeg, '-hide_banner', '-v', 'error', '-nostdin',
    '-i', source, ...extraInputs, ...options, output], { cwd: root, signal: AbortSignal.timeout(30000), stage: 'fixture' })
  return output
}
const context = () => ({ work: root, signal: AbortSignal.timeout(30000) })

test('anamorphic source uses display aspect ratio, including when rotated', async () => {
  const sar = await variant('sar.mp4', ['-vf', 'setsar=2', '-c:v', 'mpeg4', '-q:v', '5'])
  const info = await service.probe(sar, programs, context())
  assert.equal(info.width / info.height, 640 / 180)
  const gif = await service.makeGif({ source: sar, end: 0.5 })
  assert.deepEqual([gif.width, gif.height], [640, 180])
  const rotated = join(root, 'rotated.mp4')
  await service.runtime.run([programs.ffmpeg, '-hide_banner', '-v', 'error', '-nostdin', '-display_rotation', '90', '-i', sar,
    '-c', 'copy', rotated],
  { cwd: root, signal: AbortSignal.timeout(30000), stage: 'fixture' })
  const portrait = await service.makeGif({ source: rotated, end: 0.5 })
  assert.deepEqual([portrait.width, portrait.height], [180, 640])
})

test('low-FPS and short clips keep source speed without unnecessary frame duplication', async () => {
  const low = await variant('low.mkv', ['-vf', 'fps=2', '-c:v', 'ffv1'])
  const gif = await service.makeGif({ source: low, end: 2 })
  assert.deepEqual([gif.fps, gif.frame_count, gif.duration_seconds], [2, 4, 2])
  const short = await service.makeGif({ source, start: 0.1, end: 0.35 })
  assert.equal(short.frame_count, 5)
  assert.equal(short.duration_seconds, 0.25)
})

test('variable-FPS input is sampled using timestamps with a valid clip duration', async () => {
  const vfr = await variant('vfr.mkv', ['-vf', 'setpts=if(lt(N\\,20)\\,N/(20*TB)\\,(1+(N-20)/10)/TB)',
    '-fps_mode', 'vfr', '-c:v', 'ffv1'])
  const result = await service.makeGif({ source: vfr, start: 0.5, end: 2.5 })
  assert.equal(result.status, 'completed')
  assert(Math.abs(result.duration_seconds - 2) < 0.15)
  assert(result.fps <= 20)
})

test('probe distinguishes real audio from a silent source; HDR remains rejected', async () => {
  assert.equal((await service.probe(source, programs, context())).has_audio, false)
  const audio = await variant('audio.mkv', ['-c:v', 'ffv1', '-c:a', 'pcm_s16le', '-shortest'],
    ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=3'])
  const info = await service.probe(audio, programs, context())
  assert.equal(info.has_audio, true)
  assert.equal(info.audio_codec, 'pcm_s16le')
  const hdr = await variant('hdr.mp4', ['-vf', 'format=yuv420p,setparams=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc',
    '-c:v', 'mpeg4', '-q:v', '5', '-movflags', '+write_colr'])
  const metadata = JSON.parse(await service.runtime.run([programs.ffprobe, '-v', 'error', '-show_streams', '-of', 'json', hdr],
    { cwd: root, signal: AbortSignal.timeout(30000), stage: 'fixture' }))
  assert.equal(metadata.streams[0].color_transfer, 'smpte2084', JSON.stringify(metadata.streams[0]))
  await assert.rejects(service.makeGif({ source: hdr, end: 0.5 }), error => error.code === 'hdr_unsupported')
})

test('unknown pixel ratio and non-right-angle rotation fail before encoding', async () => {
  const s = new AmberService({ subprocess: {}, workingDirectory: {} })
  for (const metadata of [{ sample_aspect_ratio: 'bad' }, { side_data_list: [{ rotation: 45 }] }]) {
    s.runtime.run = async () => JSON.stringify({ streams: [{ codec_type: 'video', width: 320, height: 180,
      avg_frame_rate: '20/1', ...metadata }], format: { duration: 1, size: 1000 } })
    await assert.rejects(s.probe('fixture', programs, context()), /aspect_unsupported|rotation_unsupported/)
  }
  await s.close()
})
