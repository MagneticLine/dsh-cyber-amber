// Offline yt-dlp protocol fixture. Never connects to a website.
import { copyFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
const [source, ...args] = process.argv.slice(2)
const folder = args[args.indexOf('-P') + 1]
await copyFile(source, join(folder, 'media.avi'))
await writeFile(join(folder, 'media.info.json'), JSON.stringify({ title: '离线 下载测试', id: 'fixture' }))
console.log(join(folder, 'media.avi'))
