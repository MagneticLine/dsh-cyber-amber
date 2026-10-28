// Optional real-DSH probe plugin, mounted only in an isolated validation profile.
// Config: source (local video), outputDir, reportDir. Does not download or publish.
import assert from 'node:assert/strict'
import { mkdir, readdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
export const name = 'cyber-amber-host-probe'
export const inject = ['tools']

export function apply(ctx, config) {
  const controller = new AbortController()
  let running
  const timer = setTimeout(() => {
    running = (async () => {
      const report = { tools: [], calls: [] }
      const call = async (name, args, signal = controller.signal) => {
        const result = await ctx.tools.execute({ name, arguments: args, signal,
          callId: `amber-probe-${report.calls.length}` })
        report.calls.push({ name, result })
        return result
      }
      try {
        for (const name of ['amber_download_video', 'amber_make_gif']) {
          assert(ctx.tools.get(name), `Missing tool ${name}`)
          report.tools.push(name)
        }
        const base = { source: config.source, start: config.start ?? 0, end: config.end ?? 1, output_dir: config.outputDir }
        const made = await call('amber_make_gif', base)
        assert.equal(made.isError, false)
        assert.equal(made.value.status, 'completed')
        assert(made.value.path.endsWith('.gif'))
        const tiny = await call('amber_make_gif', { ...base, max_size_mb: 0.000001 })
        assert.equal(tiny.isError, false)
        assert.equal(tiny.value.status, 'needs_adjustment')
        const invalid = await call('amber_make_gif', { ...base, fps: '20' })
        assert.equal(invalid.isError, true)
        assert.equal(invalid.error.info.code, 'INVALID_ARGS')
        assert.deepEqual((await readdir(config.outputDir)).filter(n => n.startsWith('.amber-')), [])
        report.status = 'passed'
      } catch (error) { report.status = 'failed'; report.error = String(error.stack || error) }
      await mkdir(config.reportDir, { recursive: true })
      await writeFile(join(config.reportDir, 'amber-host-report.json'), JSON.stringify(report, null, 2) + '\n', 'utf8')
      console.log(`AMBER_HOST_PROBE_${report.status.toUpperCase()}`)
    })()
  }, 300)
  ctx.effect(() => async () => { clearTimeout(timer); controller.abort(); await running })
}
