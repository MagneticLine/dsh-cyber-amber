import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { bundledExecutable, VENDOR_ROOT } from '../lib/binaries.js'
import { Runtime } from '../lib/runtime.js'
import { testFolder, removeTestFolder } from './support/fixtures.mjs'

let root
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
before(async () => { root = await testFolder('binaries-') })
after(async () => { await removeTestFolder(root) })

async function fixture(name, tamper = false, missing = false) {
  const path = join(root, name)
  await mkdir(path)
  const exe = Buffer.from('test exe'), dll = Buffer.from('test dll')
  await writeFile(join(path, 'ffmpeg.exe'), exe)
  if (!missing) await writeFile(join(path, 'shared.dll'), tamper ? Buffer.from('bad DLL!') : dll)
  await writeFile(join(path, 'manifest.json'), JSON.stringify({ platform: 'win32', arch: 'x64',
    binaries: { ffmpeg: 'ffmpeg.exe' }, files: {
      'ffmpeg.exe': { component: 'ffmpeg', bytes: exe.length, sha256: hash(exe) },
      'shared.dll': { component: 'ffmpeg', bytes: dll.length, sha256: hash(dll) },
    } }))
  return { root: path, platform: 'win32', arch: 'x64' }
}

test('bundled engine verifies its shared DLLs before returning an absolute path', async () => {
  const options = await fixture('good')
  assert.equal(await bundledExecutable('ffmpeg', options), join(options.root, 'ffmpeg.exe'))
  assert.equal(await bundledExecutable('ffmpeg', { ...options, platform: 'linux' }), null)
})

test('tampered or missing DLLs fail rather than silently choosing PATH versions', async () => {
  await assert.rejects(bundledExecutable('ffmpeg', await fixture('tamper', true)), /bundle_checksum_failed/)
  await assert.rejects(bundledExecutable('ffmpeg', await fixture('missing', false, true)), /bundle_missing/)
})

test('explicit overrides are authoritative even when the bundle is incomplete', async () => {
  const seen = []
  const runtime = new Runtime({ resolveExecutable: async name => { seen.push(name); return name } }, { root: join(root, 'absent') })
  assert.equal(await runtime.executable('external-ffmpeg', 'ffmpeg', new AbortController().signal), 'external-ffmpeg')
  assert.deepEqual(seen, ['external-ffmpeg'])
})

test('release manifest contains all four pinned engines and the onedir Python support files', async () => {
  const manifest = JSON.parse(await readFile(join(VENDOR_ROOT, 'manifest.json'), 'utf8'))
  assert.deepEqual(Object.keys(manifest.binaries).sort(), ['ffmpeg', 'ffprobe', 'gifski', 'yt-dlp'])
  assert.equal(manifest.components['yt-dlp'].version, '2026.10.26')
  assert.equal(manifest.components.gifski.version, '1.34.0')
  assert(Object.keys(manifest.files).some(name => name.includes('yt-dlp/_internal/python')))
  for (const name of Object.keys(manifest.binaries)) {
    const path = await bundledExecutable(name)
    assert(resolve(path).startsWith(resolve(VENDOR_ROOT)))
  }
})
