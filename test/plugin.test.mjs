import './support/register.mjs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
const { apply, Config, inject, render, resultSchema } = await import('../lib/index.js')

test('entry registers exactly two globally visible, prefixed tools', () => {
  const definitions = [], effects = []
  apply({ subprocess: {}, workingDirectory: {}, tools: { register: t => definitions.push(t) },
    effect: cb => effects.push(cb) }, {})
  assert.deepEqual(definitions.map(t => t.name), ['amber_download_video', 'amber_make_gif'])
  assert.deepEqual(inject, ['tools', 'subprocess', 'workingDirectory'])
  assert(Config)
  assert.equal(effects.length, 1)
  for (const t of definitions) {
    assert.equal(t.output.schema, resultSchema)
    assert.equal(typeof t.execute, 'function')
    assert.equal(t.output.render, render)
  }
  assert(definitions[0].parameters.url.required)
  assert(definitions[1].parameters.source.required)
  assert(definitions[1].parameters.start.oneOf)
})

test('needs_adjustment rendering exposes measurements and requests a choice', () => {
  const out = render({}, { status: 'needs_adjustment', limit_bytes: 3000000, smallest_bytes: 4000000,
    width: 640, height: 400, fps: 20, start: 2, end: 6,
    attempts: [{ quality: 50, bytes: 4000000 }], suggestions: [{ explanation: '降低尺寸，仍需验证' }] })
  assert(out[0].text.includes('3000000'))
  assert(out[0].text.includes('4000000'))
  assert(out[0].text.includes('不要自行重试'))
  assert(out[0].text.includes('不保证达标'))
})

test('success rendering retains a usable path without claiming external publication', () => {
  const out = render({}, { status: 'completed', path: 'F:/out/a.gif', source: 'BV source',
    width: 640, height: 400, fps: 20, duration_seconds: 4, bytes: 2990000,
    quality: 50, motion_quality: 75, lossy_quality: 50 })
  assert(out[0].text.includes('F:/out/a.gif'))
  assert(out[0].text.includes('Q50/M75/L50'))
  assert(out[0].text.includes('未上传或发布'))
})
