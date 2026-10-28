// Test-only stand-in for the DSH subprocess seam. Production never uses child_process.
import { spawn } from 'node:child_process'
import { access } from 'node:fs/promises'
import { delimiter, isAbsolute, join } from 'node:path'

export function nativeRuntime() {
  const live = new Set(), seen = []
  return {
    live, seen,
    async resolveExecutable(name) {
      const candidates = isAbsolute(name) ? [name] : (process.env.PATH || '').split(delimiter)
        .flatMap(dir => [join(dir, name), ...(process.platform === 'win32' ? [join(dir, name + '.exe')] : [])])
      for (const candidate of candidates) {
        try { await access(candidate); return candidate } catch {}
      }
      throw new Error('executable not found')
    },
    spawn(spec) {
      seen.push(spec)
      const mode = name => typeof spec.stdio[name] === 'object' ? 'pipe' : spec.stdio[name]
      const child = spawn(spec.argv[0], spec.argv.slice(1), { cwd: spec.cwd,
        stdio: ['stdin', 'stdout', 'stderr'].map(mode), windowsHide: true })
      live.add(child)
      const collected = {}
      for (const key of ['stdout', 'stderr']) if (typeof spec.stdio[key] === 'object') {
        let text = '', total = 0
        child[key].on('data', chunk => { total += chunk.length; text = (text + chunk.toString()).slice(-spec.stdio[key].maxBytes) })
        collected[key] = { readFrom: () => ({ text, nextOffset: total,
          lossy: total > spec.stdio[key].maxBytes }) }
      }
      const terminate = () => { if (child.exitCode === null && child.signalCode === null) child.kill() }
      const abort = () => terminate()
      spec.signal.addEventListener('abort', abort, { once: true })
      const done = new Promise((resolve, reject) => {
        child.once('error', reject)
        child.once('close', (exitCode, signal) => {
          spec.signal.removeEventListener('abort', abort)
          live.delete(child)
          resolve({ exitCode, signal })
        })
      })
      done.catch(() => {})
      if (spec.signal.aborted) terminate()
      return { stdin: child.stdin, stdout: child.stdout, stderr: child.stderr,
        collected, done, terminate, waitForExit: () => done.catch(() => {}) }
    },
  }
}
