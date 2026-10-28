// Opt-in real-network host acceptance probe; mount only in an isolated profile.
import assert from 'node:assert/strict'
import { mkdir, readdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
export const name = 'cyber-amber-bundle-probe'
export const inject = ['tools']
export function apply(ctx, config) {
  let running
  const controller = new AbortController()
  const timer = setTimeout(() => {
    running = (async () => {
      const report = { calls: [] }
      const call = async (name, args) => {
        const result = await ctx.tools.execute({ name, arguments: { ...args, output_dir: config.outputDir },
          callId: `bundle-${report.calls.length}`, signal: controller.signal })
        report.calls.push({ name, result })
        assert.equal(result.isError, false, JSON.stringify(result.error))
        return result.value
      }
      try {
        let source = config.source
        if (config.url) source = (await call('amber_download_video', { url: config.url })).path
        assert(source, 'A source or opt-in download URL is required')
        const gif = await call('amber_make_gif', { source, start: 2, end: 6, max_size_mb: 3 })
        assert.equal(gif.status, 'completed')
        assert(gif.bytes <= 3000000)
        assert.equal(gif.duration_seconds, 4)
        const tiny = await call('amber_make_gif', { source, start: 2, end: 3, max_size_mb: 0.000001 })
        assert.equal(tiny.status, 'needs_adjustment')
        report.temporary_folders = (await readdir(config.outputDir)).filter(n => n.startsWith('.amber-'))
        assert.deepEqual(report.temporary_folders, [])
        report.status = 'passed'
      } catch (error) { report.status = 'failed'; report.error = String(error.stack || error) }
      await mkdir(config.reportDir, { recursive: true })
      await writeFile(join(config.reportDir, config.reportName || 'bundle-host-report.json'), JSON.stringify(report, null, 2) + '\n', 'utf8')
      console.log(`AMBER_BUNDLE_PROBE_${report.status.toUpperCase()}`)
    })()
  }, 300)
  ctx.effect(() => async () => { clearTimeout(timer); controller.abort(); await running })
}
