import type { DetectionResult, PaintSeries } from '../types.ts'
import { allSeries } from '../data/index.ts'

/**
 * Given a color code string, detect which series it belongs to.
 * Returns the best match based on prefixes.
 */
export function detectSeries(code: string): DetectionResult {
  const trimmed = code.trim().toUpperCase()

  // Try longest affix first so more specific matches win.
  const sorted = [...allSeries].sort(
    (a, b) =>
      Math.max(...[...(b.prefixes ?? []), ...(b.suffixes ?? []), ''].map(v => v.length)) -
      Math.max(...[...(a.prefixes ?? []), ...(a.suffixes ?? []), ''].map(v => v.length)),
  )

  for (const series of sorted) {
    for (const prefix of series.prefixes ?? []) {
      if (prefix && trimmed.startsWith(prefix.toUpperCase())) {
        return { series, confidence: 'certain', matchingPrefix: prefix }
      }
    }

    for (const suffix of series.suffixes ?? []) {
      if (suffix && trimmed.endsWith(suffix.toUpperCase())) {
        return { series, confidence: 'certain', matchingPrefix: suffix }
      }
    }
  }

  return { series: null, confidence: 'unknown', matchingPrefix: '' }
}

/**
 * Try to auto-detect the dominant series from a multiline input string.
 * Returns the series if all non-empty lines agree, otherwise null.
 */
export function autoDetectFromInput(input: string): DetectionResult {
  const lines = input
    .split('\n')
    .map(l => l.trim())
    .filter(l => l.length > 0)

  if (lines.length === 0) return { series: null, confidence: 'unknown', matchingPrefix: '' }

  const detections = lines.map(detectSeries).filter(d => d.series !== null)

  if (detections.length === 0) return { series: null, confidence: 'unknown', matchingPrefix: '' }

  // Check if all detected lines agree on the same series
  const firstSeries = detections[0].series
  const allSame = detections.every(d => d.series?.series === firstSeries?.series)

  if (allSame) {
    return { series: firstSeries, confidence: 'certain', matchingPrefix: detections[0].matchingPrefix }
  }

  // Mixed result — return the most common one
  const counts = new Map<string, { series: PaintSeries; count: number }>()
  for (const d of detections) {
    if (!d.series) continue
    const key = d.series.series
    const existing = counts.get(key)
    if (existing) existing.count++
    else counts.set(key, { series: d.series, count: 1 })
  }

  const best = [...counts.values()].sort((a, b) => b.count - a.count)[0]
  return { series: best.series, confidence: 'possible', matchingPrefix: '' }
}

/**
 * Strip the series prefix from a code to get just the numeric/id part.
 * e.g. "70.950" with prefix "70." → "950";  "XF-1" with prefix "XF-" → "XF-1" (keep as-is)
 */
export function normalizeId(code: string, series: PaintSeries): string {
  const trimmed = code.trim()
  const sortedPrefixes = [...(series.prefixes ?? [])].sort((a, b) => b.length - a.length)
  const sortedSuffixes = [...(series.suffixes ?? [])].sort((a, b) => b.length - a.length)

  let normalized = trimmed

  for (const prefix of sortedPrefixes) {
    if (prefix && normalized.toLowerCase().startsWith(prefix.toLowerCase())) {
      normalized = normalized.slice(prefix.length)
      break
    }
  }

  for (const suffix of sortedSuffixes) {
    if (suffix && normalized.toLowerCase().endsWith(suffix.toLowerCase())) {
      normalized = normalized.slice(0, normalized.length - suffix.length)
      break
    }
  }

  return normalized
}
