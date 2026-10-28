export function suggestions(params, bytes, limit) {
  const ratio = Math.min(1, limit / Math.max(1, bytes))
  const edge = Math.max(128, Math.floor(Math.max(params.width, params.height) * Math.sqrt(ratio) * 0.95 / 16) * 16)
  const fps = Math.max(1, Math.floor(params.fps * ratio * 0.95))
  const items = []
  if (edge < Math.max(params.width, params.height)) items.push({
    change: 'long_edge', value: edge, verified: false,
    explanation: `可先试长边${edge}，保持帧率；文字和细节会变小。按像素数量粗估，实际体积须重试验证。`,
  })
  if (fps < params.fps) items.push({ change: 'fps', value: fps, verified: false,
    explanation: `可先试${fps}fps，保持尺寸；动作连续性可能下降。按帧数粗估，实际体积须重试验证。` })
  if (params.quality > 1 || params.lossy_quality > 1) items.push({
    change: 'quality_and_lossy_quality', value: Math.max(1, Math.min(params.quality, params.lossy_quality) - 10),
    verified: false,
    explanation: `可在用户同意后先试Q${Math.max(1, Math.min(params.quality, params.lossy_quality) - 10)}/L${Math.max(1, Math.min(params.quality, params.lossy_quality) - 10)}；可能增加噪点、色块等量化失真，实际体积须重试验证。`,
  })
  return items
}

/** Size is measured, never inferred from an MP4 bitrate. At most ten distinct encodes. */
export async function fitBudget(params, encode, remove) {
  const trials = new Map()
  let best = null
  let smallest = null
  const limit = params.max_bytes
  const coupled = params.quality === params.lossy_quality

  async function attempt(q) {
    if (trials.has(q)) return trials.get(q)
    if (trials.size >= 10) return null
    const settings = { ...params, quality: q, lossy_quality: coupled ? q : params.lossy_quality }
    const result = await encode(settings)
    const record = { quality: q, lossy_quality: settings.lossy_quality,
      motion_quality: params.motion_quality, bytes: result.bytes }
    trials.set(q, record)
    if (!smallest || record.bytes < smallest.bytes) smallest = record
    const fits = !limit || result.bytes <= limit
    if (fits && (!best || q > best.quality)) {
      if (best) await remove(best.result)
      best = { ...record, result }
    } else await remove(result)
    return record
  }

  const first = await attempt(params.quality)
  if (limit && first.bytes > limit && coupled && params.min_quality < params.quality) {
    const floor = await attempt(params.min_quality)
    if (floor.bytes <= limit) {
      let lo = params.min_quality + 1, hi = params.quality - 1
      while (lo <= hi && trials.size < 8) {
        const mid = Math.floor((lo + hi) / 2)
        const value = await attempt(mid)
        if (value.bytes <= limit) lo = mid + 1
        else hi = mid - 1
      }
      // Real sizes are not perfectly monotonic. Check immediate boundary neighbours too.
      const boundary = best.quality
      for (const q of [boundary + 1, boundary + 2, boundary - 1]) {
        if (q >= params.min_quality && q <= params.quality && trials.size < 10) await attempt(q)
      }
    }
  }
  if (best) return { status: 'completed', result: best.result, attempts: [...trials.values()] }
  return { status: 'needs_adjustment', limit_bytes: limit, smallest_bytes: smallest.bytes,
    attempts: [...trials.values()], suggestions: suggestions({ ...params, ...smallest }, smallest.bytes, limit) }
}
