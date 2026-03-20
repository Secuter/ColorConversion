import type { ConversionResult, MatchedCorrespondence, PaintColor, PaintSeries } from '../types.ts'
import { allSeries } from '../data/index.ts'
import { normalizeId, detectSeries } from './useColorDetection.ts'

/**
 * Find a color by id within a series.
 * Handles prefix-stripped and full-code lookups.
 */
function findColorInSeries(id: string, series: PaintSeries): PaintColor | null {
  const rawUpper = id.trim().toUpperCase()
  const exact = series.colors.find(c => c.id.trim().toUpperCase() === rawUpper)
  if (exact) return exact

  const normalized = normalizeId(id, series).trim().toUpperCase()
  return (
    series.colors.find(c => normalizeId(c.id, series).trim().toUpperCase() === normalized) ??
    null
  )
}

/**
 * Build a MatchedCorrespondence from a color in a series.
 */
function toMatch(
  color: PaintColor,
  series: PaintSeries,
  source: 'direct' | 'reverse',
  note?: string,
): MatchedCorrespondence {
  return {
    manufacturer: series.manufacturer,
    series: series.series,
    id: color.id,
    name: color.name,
    rgb: color.rgb,
    source,
    note,
  }
}

/**
 * Convert a list of color codes from the source series to target correspondences.
 *
 * @param codes        Raw input codes (one per line)
 * @param sourceSeries The series to look up colors in
 * @param targetFilter Optional manufacturer filter ("" or undefined = all)
 */
export function convertColors(
  codes: string[],
  sourceSeries: PaintSeries,
  targetManufacturers?: string[],
): ConversionResult[] {
  const uniqueCodes: string[] = []
  const seenInputs = new Set<string>()

  for (const rawCode of codes) {
    const code = rawCode.trim()
    if (!code) continue

    const dedupeKey = normalizeId(code, sourceSeries).trim().toUpperCase()
    if (seenInputs.has(dedupeKey)) continue
    seenInputs.add(dedupeKey)
    uniqueCodes.push(code)
  }

  return uniqueCodes.map(rawCode => {
    const code = rawCode.trim()
    if (!code)
      return { inputCode: code, normalizedId: '', sourceColor: null, sourceSeries, correspondences: [] }

    // Normalize: strip leading prefix (e.g. "70.") so we match against bare id "950"
    const normalizedId = normalizeId(code, sourceSeries)
    const normalizedIdUpper = normalizedId.toUpperCase()

    const sourceColor = findColorInSeries(code, sourceSeries)

    if (!sourceColor) {
      return { inputCode: code, normalizedId, sourceColor: null, sourceSeries, correspondences: [] }
    }

    const matches: MatchedCorrespondence[] = []
    const seen = new Set<string>() // deduplicate by "series:id"

    // 1. Direct correspondences from the source color
    for (const corr of sourceColor.correspondences) {
      if (targetManufacturers?.length && !targetManufacturers.includes(corr.manufacturer)) continue
      const targetSeries = allSeries.find(s => s.series === corr.series)
      if (!targetSeries) continue
      const targetColor = findColorInSeries(corr.id, targetSeries)
      if (!targetColor) continue
      const key = `${targetSeries.manufacturer}|${targetSeries.series}|${normalizeId(targetColor.id, targetSeries).toUpperCase()}`
      if (seen.has(key)) continue
      seen.add(key)
      matches.push(toMatch(targetColor, targetSeries, 'direct', corr.note))
    }

    // 2. Reverse lookup: find colors in OTHER series that list this source as a correspondence
    for (const series of allSeries) {
      if (series.series === sourceSeries.series) continue
      if (targetManufacturers?.length && !targetManufacturers.includes(series.manufacturer)) continue

      for (const color of series.colors) {
        for (const corr of color.correspondences) {
          const matchesSeries =
            corr.series === sourceSeries.series ||
            corr.manufacturer === sourceSeries.manufacturer
          const corrNormUpper = normalizeId(corr.id, sourceSeries).toUpperCase()
          if (matchesSeries && corrNormUpper === normalizedIdUpper) {
            const key = `${series.manufacturer}|${series.series}|${normalizeId(color.id, series).toUpperCase()}`
            if (seen.has(key)) continue
            seen.add(key)
            matches.push(toMatch(color, series, 'reverse'))
          }
        }
      }
    }

    const uniqueMatches = matches.filter((match, index, list) => {
      const matchKey = `${match.manufacturer}|${match.series}|${match.id.toUpperCase()}`
      return index === list.findIndex(item => `${item.manufacturer}|${item.series}|${item.id.toUpperCase()}` === matchKey)
    })

    return {
      inputCode: code,
      normalizedId,
      sourceColor,
      sourceSeries,
      correspondences: uniqueMatches,
    }
  })
}

/**
 * Convert a list of color codes with automatic series detection per code.
 * Each code is detected individually, allowing mixed series in a single input.
 *
 * @param codes              Raw input codes (one per line)
 * @param targetManufacturers Optional manufacturer filter
 */
export function convertColorsMultipleSeries(
  codes: string[],
  targetManufacturers?: string[],
): ConversionResult[] {
  const results: ConversionResult[] = []
  const seenInputs = new Set<string>()

  for (const code of codes) {
    const trimmed = code.trim()
    if (!trimmed) {
      continue
    }

    // Detect the series for this specific code
    const detected = detectSeries(trimmed)

    if (detected.series) {
      const dedupeKey = `${detected.series.manufacturer}|${detected.series.series}|${normalizeId(trimmed, detected.series).trim().toUpperCase()}`
      if (seenInputs.has(dedupeKey)) continue
      seenInputs.add(dedupeKey)
    } else {
      const dedupeKey = `unknown|${trimmed.toUpperCase()}`
      if (seenInputs.has(dedupeKey)) continue
      seenInputs.add(dedupeKey)
    }

    if (!detected.series) {
      results.push({
        inputCode: trimmed,
        normalizedId: '',
        sourceColor: null,
        sourceSeries: null,
        correspondences: [],
      })
      continue
    }

    // Convert using the detected series
    const converted = convertColors([trimmed], detected.series, targetManufacturers)
    results.push(...converted)
  }

  return results
}
