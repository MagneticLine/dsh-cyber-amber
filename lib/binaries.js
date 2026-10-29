import { createReadStream } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { isAbsolute, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { AmberError } from './options.js';
export const VENDOR_ROOT = fileURLToPath(new URL('../vendor/', import.meta.url));
const verified = new Map();
function plainObject(value) {
    if (value === null || typeof value !== 'object' || Array.isArray(value))
        return false;
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
}
function invalidManifest() {
    return new AmberError('bundle_invalid', '插件依赖清单格式无效，请重新安装完整插件包。');
}
/** Validate the fields consumed at the runtime JSON boundary. */
function readManifest(text) {
    const value = JSON.parse(text);
    if (!plainObject(value) || typeof value.platform !== 'string' || typeof value.arch !== 'string') {
        throw invalidManifest();
    }
    const manifest = { platform: value.platform, arch: value.arch };
    if (value.binaries !== undefined) {
        if (!plainObject(value.binaries))
            throw invalidManifest();
        const entries = [];
        for (const [name, path] of Object.entries(value.binaries)) {
            if (typeof path !== 'string')
                throw invalidManifest();
            entries.push([name, path]);
        }
        manifest.binaries = Object.fromEntries(entries);
    }
    if (value.files !== undefined) {
        if (!plainObject(value.files))
            throw invalidManifest();
        const entries = [];
        for (const [path, entry] of Object.entries(value.files)) {
            if (!plainObject(entry) || typeof entry.component !== 'string'
                || typeof entry.bytes !== 'number' || !Number.isSafeInteger(entry.bytes) || entry.bytes < 0
                || typeof entry.sha256 !== 'string' || !/^[a-f\d]{64}$/i.test(entry.sha256)) {
                throw invalidManifest();
            }
            entries.push([path, { component: entry.component, bytes: entry.bytes, sha256: entry.sha256 }]);
        }
        manifest.files = Object.fromEntries(entries);
    }
    return manifest;
}
export async function hashFile(path) {
    const hash = createHash('sha256');
    for await (const chunk of createReadStream(path))
        hash.update(chunk);
    return hash.digest('hex');
}
export function contained(root, name) {
    const path = resolve(root, name);
    const rel = relative(resolve(root), path);
    if (!rel || rel.startsWith('..') || isAbsolute(rel))
        throw new AmberError('bundle_invalid', '依赖清单包含无效路径，请重新安装完整插件包。');
    return path;
}
export async function verifyFile(root, name, entry) {
    const path = contained(root, name);
    let info;
    try {
        info = await stat(path);
    }
    catch {
        throw new AmberError('bundle_missing', `插件内置依赖缺失：${name}；请重新安装完整tgz包，或明确配置外部程序路径。`);
    }
    const signature = `${info.size}:${info.mtimeMs}:${info.ctimeMs}`;
    const key = `${path}:${entry.sha256}`;
    if (verified.get(key) === signature)
        return path;
    if (!info.isFile() || info.size !== entry.bytes || await hashFile(path) !== entry.sha256) {
        throw new AmberError('bundle_checksum_failed', `插件内置依赖校验失败：${name}；已停止执行，请重新安装完整插件包。`);
    }
    verified.set(key, signature);
    return path;
}
/** No downloads, extraction, installer hooks or automatic updates occur at runtime. */
export async function bundledExecutable(name, options = {}) {
    const root = options.root ?? VENDOR_ROOT;
    const platform = options.platform ?? process.platform, arch = options.arch ?? process.arch;
    let manifest;
    try {
        manifest = readManifest(await readFile(resolve(root, 'manifest.json'), 'utf8'));
    }
    catch (error) {
        if (error instanceof AmberError && error.code === 'bundle_invalid')
            throw error;
        throw new AmberError('bundle_missing', '缺少插件依赖清单；请安装完整tgz包，源码开发者需先执行依赖准备脚本。');
    }
    if (platform !== manifest.platform || arch !== manifest.arch)
        return null;
    const file = manifest.binaries?.[name];
    const selected = file ? manifest.files?.[file] : undefined;
    if (!file || !selected || !manifest.files)
        throw new AmberError('bundle_invalid', `依赖清单缺少${name}，请重新安装完整插件包。`);
    const component = selected.component;
    for (const [path, entry] of Object.entries(manifest.files)) {
        if (entry.component === component)
            await verifyFile(root, path, entry);
    }
    return verifyFile(root, file, selected);
}
//# sourceMappingURL=binaries.js.map