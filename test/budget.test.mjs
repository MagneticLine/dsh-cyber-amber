import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fitBudget } from '../lib/budget.js'

const defaults = { quality: 75, lossy_quality: 75, motion_quality: 75, min_quality: 50,
  width: 640, height: 400, fps: 20, max_bytes: 0 }

function encoder(bytes) {
  const live = new Set(), attempts = []
  return { live, attempts,
    async encode(p) {
      attempts.push(p)
      const output = { path: String(p.quality), bytes: bytes(p.quality), quality: p.quality }
      live.add(output.path)
      return output
    },
    async remove(value) { assert(live.delete(value.path)) },
  }
}

test('no target encodes exactly once; an already-fitting target never raises quality', async () => {
  for (const max_bytes of [0, 1000]) {
    const e = encoder(() => 900)
    const result = await fitBudget({ ...defaults, max_bytes }, e.encode, e.remove)
    assert.equal(result.status, 'completed')
    assert.equal(e.attempts.length, 1)
    assert.deepEqual([...e.live], ['75'])
  }
})

test('bounded search checks neighbouring integers and retains only the best tested fit', async () => {
  const e = encoder(q => q * 1000)
  const result = await fitBudget({ ...defaults, max_bytes: 62000 }, e.encode, e.remove)
  assert.equal(result.result.quality, 62)
  assert(result.attempts.some(a => a.quality === 63))
  assert(result.attempts.length <= 10)
  assert.equal(new Set(result.attempts.map(a => a.quality)).size, result.attempts.length)
  assert.deepEqual([...e.live], ['62'])
  for (const p of e.attempts) {
    assert.equal(p.quality, p.lossy_quality)
    assert(p.quality >= 50 && p.quality <= 75)
    assert.deepEqual([p.width, p.height, p.fps, p.motion_quality], [640, 400, 20, 75])
  }
})

test('small non-monotonic boundary dip is measured rather than assumed', async () => {
  const e = encoder(q => q === 64 ? 61000 : q * 1000)
  const result = await fitBudget({ ...defaults, max_bytes: 62000 }, e.encode, e.remove)
  assert.equal(result.result.quality, 64)
})

test('too-small budget returns measured failure plus three explicitly unverified tradeoffs', async () => {
  const e = encoder(q => q * 1000)
  const result = await fitBudget({ ...defaults, max_bytes: 30000 }, e.encode, e.remove)
  assert.equal(result.status, 'needs_adjustment')
  assert.equal(result.smallest_bytes, 50000)
  assert.equal(result.suggestions.length, 3)
  assert(result.suggestions.every(s => s.verified === false && s.explanation.includes('验证')))
  assert.equal(e.live.size, 0)
  assert(e.attempts.every(p => p.quality >= 50))
})

test('independent Q/L settings are never silently rewritten', async () => {
  const e = encoder(() => 1000)
  const result = await fitBudget({ ...defaults, lossy_quality: 100, max_bytes: 900 }, e.encode, e.remove)
  assert.equal(result.status, 'needs_adjustment')
  assert.equal(e.attempts.length, 1)
  assert.equal(e.attempts[0].lossy_quality, 100)
})

test('explicit low quality below the default floor is respected', async () => {
  const e = encoder(() => 1000)
  const result = await fitBudget({ ...defaults, quality: 40, lossy_quality: 40, min_quality: 40, max_bytes: 900 }, e.encode, e.remove)
  assert.equal(result.status, 'needs_adjustment')
  assert.deepEqual(e.attempts.map(p => p.quality), [40])
})
