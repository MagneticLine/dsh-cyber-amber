// Deterministic real-host acceptance. No LLM, credentials, external platform or desktop UI.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createReadStream } from 'node:fs'
import { mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

export const name = 'cyber-amber-rc-probe'
export const inject = ['tools', 'subprocess']
export function apply(ctx, config) {
  const controller = new AbortController()
  let running
  const timer = setTimeout(() => {
    running = (async () => {
      const report = { calls: [], external_network: false, overrides: false }
      let server
      const call = async (name, args, signal = controller.signal) => {
        const result = await ctx.tools.execute({ name, arguments: { ...args, output_dir: config.outputDir },
          callId: `amber-rc-${report.calls.length}`, signal })
        report.calls.push({ name, result })
        return result
      }
      try {
        await mkdir(config.outputDir, { recursive: true })
        const pkg = JSON.parse(await readFile(join(config.packageRoot, 'package.json'), 'utf8'))
        report.version = pkg.version
        const { Config } = await import(pathToFileURL(join(config.packageRoot, 'lib/index.js')).href)
        assert.equal(Config({}).quality, 75)
        for (const invalid of [{ fps: 0 }, { fps: 1.5 }, { maxPending: 0 }, { quality: 101 }]) {
          assert.throws(() => Config(invalid))
        }
        report.real_config_validation = true
        const source = await stat(config.source)
        server = createServer((request, response) => {
          response.writeHead(200, { 'Content-Type': 'video/mp4', 'Content-Length': source.size })
          if (request.method === 'HEAD') response.end()
          else createReadStream(config.source).pipe(response)
        })
        await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
        const url = `http://127.0.0.1:${server.address().port}/input.mp4?token=amber-secret-fixture`
        const downloaded = await call('amber_download_video', { url })
        assert.equal(downloaded.isError, false, JSON.stringify(downloaded.error))
        assert.equal(downloaded.value.status, 'downloaded')
        assert.equal(typeof downloaded.value.has_audio, 'boolean')
        assert(!JSON.stringify(downloaded).includes('amber-secret-fixture'))
        const base = { source: downloaded.value.path, start: 2, end: 6, max_size_mb: 3 }
        const gif = await call('amber_make_gif', base)
        assert.equal(gif.isError, false, JSON.stringify(gif.error))
        assert.equal(gif.value.status, 'completed')
        assert(gif.value.bytes <= 3000000)
        assert.equal(gif.value.frame_count, 80)
        assert.equal(gif.value.duration_seconds, 4)
        const manifest = JSON.parse(await readFile(join(config.packageRoot, 'vendor/manifest.json'), 'utf8'))
        const decoder = ctx.subprocess.spawn({ argv: [join(config.packageRoot, 'vendor', manifest.binaries.ffmpeg),
          '-v', 'error', '-nostdin', '-ignore_loop', '1', '-i', gif.value.path, '-f', 'null', '-'],
        cwd: config.outputDir, signal: controller.signal, graceMs: 1000,
        stdio: { stdin: 'ignore', stdout: { maxBytes: 1 }, stderr: { maxBytes: 65536 } } })
        try { assert.equal((await decoder.done).exitCode, 0, 'Independent full GIF decode failed') }
        finally { decoder.terminate(); await decoder.waitForExit() }
        const bytes = await readFile(gif.value.path)
        assert.equal(bytes.subarray(0, 6).toString(), 'GIF89a')
        assert.equal(bytes.at(-1), 0x3b)
        assert(bytes.includes(Buffer.from('NETSCAPE2.0\x03\x01\x00\x00\x00', 'binary')))
        report.independent_full_gif_decode = true
        const tiny = await call('amber_make_gif', { ...base, end: 3, max_size_mb: 0.000001 })
        assert.equal(tiny.value.status, 'needs_adjustment')
        const invalid = await call('amber_make_gif', { ...base, fps: '20' })
        assert.equal(invalid.isError, true)
        const ctl = new AbortController()
        const cancel = call('amber_make_gif', { ...base, end: 10, long_edge: 1280, fps: 30 }, ctl.signal)
        const abort = setTimeout(() => ctl.abort(), 500)
        let cancelled
        try { cancelled = await cancel } finally { clearTimeout(abort) }
        assert.equal(cancelled.isError, true)
        assert(/cancelled/i.test(JSON.stringify(cancelled)), JSON.stringify(cancelled))
        report.temporary_folders = (await readdir(config.outputDir)).filter(name => name.startsWith('.amber-'))
        assert.deepEqual(report.temporary_folders, [])
        report.status = 'passed'
      } catch (error) { report.status = 'failed'; report.error = String(error.stack || error) }
      finally { if (server) await new Promise(resolve => server.close(resolve)) }
      await mkdir(config.reportDir, { recursive: true })
      await writeFile(join(config.reportDir, 'host-rc-report.json'), JSON.stringify(report, null, 2) + '\n', 'utf8')
      console.log(`AMBER_RC_PROBE_${report.status.toUpperCase()}`)
    })()
    running.catch(error => console.error('AMBER_RC_PROBE_ERROR', error))
  }, 300)
  ctx.effect(() => async () => { clearTimeout(timer); controller.abort(); await running })
}
