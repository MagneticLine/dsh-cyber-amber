import assert from 'node:assert/strict'
import { mkdir, mkdtemp, realpath, rm, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = fileURLToPath(new URL('../../.validation/tests/', import.meta.url))
export async function testFolder(prefix) {
  await mkdir(ROOT, { recursive: true })
  return mkdtemp(join(ROOT, prefix))
}
export async function removeTestFolder(folder) {
  assert.equal(dirname(await realpath(folder)), await realpath(ROOT))
  await rm(folder, { recursive: true, force: true })
}

function chunk(id, bytes) {
  const header = Buffer.alloc(8)
  header.write(id, 0, 4, 'ascii')
  header.writeUInt32LE(bytes.length, 4)
  return Buffer.concat([header, bytes, ...(bytes.length % 2 ? [Buffer.alloc(1)] : [])])
}
function list(id, children) { return chunk('LIST', Buffer.concat([Buffer.from(id), ...children])) }

/** Deterministic uncompressed AVI: fixture creation needs no media process or OS temp access. */
export async function writeVideo(path) {
  const width = 320, height = 180, fps = 20, frames = 60, imageBytes = width * height * 3
  const avih = Buffer.alloc(56)
  for (const [offset, value] of [[0, 1000000 / fps], [4, imageBytes * fps], [16, frames],
    [24, 1], [28, imageBytes], [32, width], [36, height]]) avih.writeUInt32LE(value, offset)
  const strh = Buffer.alloc(56)
  strh.write('vidsDIB ', 0, 8, 'ascii')
  for (const [offset, value] of [[20, 1], [24, fps], [32, frames], [36, imageBytes], [40, 0xffffffff]]) strh.writeUInt32LE(value, offset)
  strh.writeUInt16LE(width, 52); strh.writeUInt16LE(height, 54)
  const strf = Buffer.alloc(40)
  strf.writeUInt32LE(40); strf.writeInt32LE(width, 4); strf.writeInt32LE(height, 8)
  strf.writeUInt16LE(1, 12); strf.writeUInt16LE(24, 14); strf.writeUInt32LE(imageBytes, 20)
  const video = []
  for (let f = 0; f < frames; f++) {
    const frame = Buffer.alloc(imageBytes)
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 3
      frame[i] = (y * 2 + f * 5) % 256
      frame[i + 1] = (x + y + f * 7) % 256
      frame[i + 2] = (x + f * 3) % 256
    }
    video.push(chunk('00db', frame))
  }
  const payload = Buffer.concat([Buffer.from('AVI '), list('hdrl', [chunk('avih', avih),
    list('strl', [chunk('strh', strh), chunk('strf', strf)])]), list('movi', video)])
  await writeFile(path, chunk('RIFF', payload))
}
