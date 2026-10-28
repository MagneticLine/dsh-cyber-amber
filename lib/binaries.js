import { createReadStream } from 'node:fs'
import { readFile, stat } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { isAbsolute, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { AmberError } from './options.js'

export const VENDOR_ROOT = fileURLToPath(new URL('../vendor/', import.meta.url))
const verified = new Map()

export async function hashFile(path) {
  const hash = createHash('sha256')
  for await (const chunk of createReadStream(path)) hash.update(chunk)
  return hash.digest('hex')
}

export function contained(root, name) {
  const path = resolve(root, name)
  const rel = relative(resolve(root), path)
  if (!rel || rel.startsWith('..') || isAbsolute(rel)) throw new AmberError('bundle_invalid', '依赖清单包含无效路径，请重新安装完整插件包。')
  return path
}

export async function verifyFile(root, name, entry) {
  const path = contained(root, name)
  let info
  try { info = await stat(path) }
  catch { throw new AmberError('bundle_missing', `插件内置依赖缺失：${name}；请重新安装完整tgz包，或明确配置外部程序路径。`) }
  const signature = `${info.size}:${info.mtimeMs}:${info.ctimeMs}`
  const key = `${path}:${entry.sha256}`
  if (verified.get(key) === signature) return path
  if (!info.isFile() || info.size !== entry.bytes || await hashFile(path) !== entry.sha256) {
    throw new AmberError('bundle_checksum_failed', `插件内置依赖校验失败：${name}；已停止执行，请重新安装完整插件包。`)
  }
  verified.set(key, signature)
  return path
}

/** No downloads, extraction, installer hooks or automatic updates occur at runtime. */
export async function bundledExecutable(name, options = {}) {
  const root = options.root ?? VENDOR_ROOT
  const platform = options.platform ?? process.platform, arch = options.arch ?? process.arch
  let manifest
  try { manifest = JSON.parse(await readFile(resolve(root, 'manifest.json'), 'utf8')) }
  catch {
    throw new AmberError('bundle_missing', '缺少插件依赖清单；请安装完整tgz包，源码开发者需先执行依赖准备脚本。')
  }
  if (platform !== manifest.platform || arch !== manifest.arch) return null
  const file = manifest.binaries?.[name]
  if (!file || !manifest.files?.[file]) throw new AmberError('bundle_invalid', `依赖清单缺少${name}，请重新安装完整插件包。`)
  const component = manifest.files[file].component
  for (const [path, entry] of Object.entries(manifest.files)) {
    if (entry.component === component) await verifyFile(root, path, entry)
  }
  return verifyFile(root, file, manifest.files[file])
}
