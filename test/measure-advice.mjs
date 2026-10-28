// Small, deterministic local direction checks. No video downloads; media is removed afterwards.
import { mkdir, mkdtemp, rm, unlink, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { AmberService } from '../lib/service.js'
import { Runtime } from '../lib/runtime.js'
import { nativeRuntime } from './support/native-runtime.mjs'

const root = resolve('.validation/advice')
await mkdir(root, { recursive: true })
const work = await mkdtemp(join(root, 'bench-'))
const subprocess = nativeRuntime(), runtime = new Runtime(subprocess)
const signal = AbortSignal.timeout(120000)
const ffmpegPath = await runtime.executable(process.env.AMBER_TEST_FFMPEG, 'ffmpeg', signal)
const ffprobePath = await runtime.executable(process.env.AMBER_TEST_FFPROBE, 'ffprobe', signal)
const gifskiPath = await runtime.executable(process.env.AMBER_TEST_GIFSKI, 'gifski', signal)
const service = new AmberService({ subprocess, workingDirectory: {} },
  { outputDir: join(work, 'results'), ffmpegPath, ffprobePath, gifskiPath })
const rows = []
try {
  const patterns = {
    text: "color=c=0x303030:s=640x400:r=20:d=2,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='Cyber Amber 0123456789 fine text details':fontsize=22:fontcolor=white:x=12:y=80",
    motion: 'testsrc2=size=640x400:rate=20:duration=2',
    gradient: "nullsrc=s=640x400:r=20:d=2,geq=r='X/W*255':g='Y/H*255':b='128+40*sin(T*3)'",
  }
  for (const [pattern, filter] of Object.entries(patterns)) {
    const source = join(work, pattern + '.mp4')
    await runtime.run([ffmpegPath, '-v', 'error', '-f', 'lavfi', '-i', filter, '-t', 2,
      '-c:v', 'mpeg4', '-q:v', 2, '-pix_fmt', 'yuv420p', source], { cwd: work, signal, stage: 'fixture' })
    for (const [variant, args] of Object.entries({
      baseline: {}, smaller: { long_edge: 480 }, fewer_frames: { fps: 10 }, lower_quality: { quality: 50 },
    })) {
      const value = await service.makeGif({ source, ...args }, { signal })
      const { path, title, source: ignored, attempts, status, ...metrics } = value
      rows.push({ pattern, variant, ...metrics })
      await unlink(path)
    }
  }
  await writeFile(join(root, 'measurements.json'), JSON.stringify({
    generated_at: new Date().toISOString(), engine: 'gifski 1.34.0',
    note: 'Three two-second synthetic SDR sources; direction checks, not universal visual rankings.', rows,
  }, null, 2) + '\n', 'utf8')
  for (const row of rows) console.log(`${row.pattern} ${row.variant}: ${row.bytes} bytes, ${row.frame_count} frames`)
} finally {
  await service.close()
  if (dirname(work) !== root) throw new Error('Refusing cleanup outside owned benchmark root')
  await rm(work, { recursive: true, force: true })
}
