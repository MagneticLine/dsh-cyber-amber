import { readFile, readdir } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { verifyFile } from '../lib/binaries.js'

const root = fileURLToPath(new URL('../vendor/', import.meta.url))
const manifest = JSON.parse(await readFile(new URL('../vendor/manifest.json', import.meta.url), 'utf8'))
for (const [name, entry] of Object.entries(manifest.files)) await verifyFile(root, name, entry)
async function checkListed(folder, prefix = 'win32-x64') {
  for (const item of await readdir(folder, { withFileTypes: true })) {
    const name = `${prefix}/${item.name}`
    if (item.isDirectory()) await checkListed(join(folder, item.name), name)
    else if (!manifest.files[name]) throw new Error(`Unlisted packaged dependency: ${name}`)
  }
}
await checkListed(join(root, 'win32-x64'))
console.log(`Verified ${Object.keys(manifest.files).length} pinned dependency files; ${manifest.platform}/${manifest.arch}`)
