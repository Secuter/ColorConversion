import type { PaintSeries } from '../types.ts'
import vallejoModelColor from './vallejo-model-color.json'
import vallejoModelAir from './vallejo-model-air.json'
import akRealColors from './ak-real-colors.json'
import mrColor from './mr-color.json'
import tamiyaAcrylic from './tamiya-acrylic.json'
import italeri from './italeri.json'
import paintLines from './paint-lines.json'

interface PaintLineMeta {
  series: string
  manufacturer: string
  prefixes?: string[]
  default_prefix?: string
  suffixes?: string[]
  default_suffix?: string
}

const paintLineMetaByKey = new Map(
  (paintLines as PaintLineMeta[]).map(line => [
    `${line.manufacturer}|${line.series}`,
    line,
  ]),
)

function withPaintLineMeta(series: PaintSeries): PaintSeries {
  const meta = paintLineMetaByKey.get(`${series.manufacturer}|${series.series}`)
  if (!meta) {
    return {
      ...series,
      suffixes: series.suffixes ?? [],
      default_suffix: series.default_suffix ?? '',
    }
  }

  return {
    ...series,
    prefixes: meta.prefixes ?? series.prefixes,
    default_prefix: meta.default_prefix ?? series.default_prefix,
    suffixes: meta.suffixes ?? series.suffixes ?? [],
    default_suffix: meta.default_suffix ?? series.default_suffix ?? '',
  }
}

export const allSeries: PaintSeries[] = [
  withPaintLineMeta(vallejoModelColor as PaintSeries),
  withPaintLineMeta(vallejoModelAir as PaintSeries),
  withPaintLineMeta(akRealColors as PaintSeries),
  withPaintLineMeta(mrColor as PaintSeries),
  withPaintLineMeta(tamiyaAcrylic as PaintSeries),
  withPaintLineMeta(italeri as PaintSeries),
]

/** All unique manufacturer names */
export const allManufacturers: string[] = [...new Set(allSeries.map(s => s.manufacturer))]
