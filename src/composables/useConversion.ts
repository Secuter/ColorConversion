import type { ConversionResult, MatchedCorrespondence, PaintColor, PaintSeries } from '../types.ts'
import { allSeries } from '../data/index.ts'
import { normalizeId } from './useColorDetection.ts'

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
  return codes.map(rawCode => {
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
      const key = `${corr.series}:${corr.id}`
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
            const key = `${series.series}:${color.id}`
            if (seen.has(key)) continue
            seen.add(key)
            matches.push(toMatch(color, series, 'reverse'))
          }
        }
      }
    }

    return {
      inputCode: code,
      normalizedId,
      sourceColor,
      sourceSeries,
      correspondences: matches,
    }
  })
}
