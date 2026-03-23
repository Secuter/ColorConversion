import type { PaintSeries } from '../types.ts'
import vallejoModelColor from './vallejo-model-color.json'
import vallejoModelAir from './vallejo-model-air.json'
import akAcrylic from './ak-acrylic.json'
import akRealColors from './ak-real-colors.json'
import ammoMig from './ammo-mig.json'
import ammoMigAtom from './ammo-mig-atom.json'
import federalStandard from './federal-standard.json'
import britishStandard from './british-standard.json'
import anaStandard from './ana-standard.json'
import rlm from './rlm.json'
import humbrolEnamel from './humbrol-enamel.json'
import mrColor from './mr-color.json'
import mrColorAqueous from './mr-color-aqueous.json'
import revellAcrylic from './revell-acrylic.json'
import revellEnamel from './revell-enamel.json'
import italeri from './italeri.json'
import paintLines from './paint-lines.json'

interface PaintLineMeta {
  series: string
  manufacturer: string
  type?: string
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
    type: meta.type,
    prefixes: meta.prefixes ?? series.prefixes,
    default_prefix: meta.default_prefix ?? series.default_prefix,
    suffixes: meta.suffixes ?? series.suffixes ?? [],
    default_suffix: meta.default_suffix ?? series.default_suffix ?? '',
  }
}

const configuredSeries: PaintSeries[] = [
  withPaintLineMeta(vallejoModelColor as PaintSeries),
  withPaintLineMeta(vallejoModelAir as PaintSeries),
  withPaintLineMeta(akAcrylic as PaintSeries),
  withPaintLineMeta(akRealColors as PaintSeries),
  withPaintLineMeta(ammoMig as PaintSeries),
  withPaintLineMeta(ammoMigAtom as PaintSeries),
  withPaintLineMeta(humbrolEnamel as PaintSeries),
  withPaintLineMeta(revellAcrylic as PaintSeries),
  withPaintLineMeta(revellEnamel as PaintSeries),
  withPaintLineMeta(federalStandard as PaintSeries),
  withPaintLineMeta(britishStandard as PaintSeries),
  withPaintLineMeta(anaStandard as PaintSeries),
  withPaintLineMeta(rlm as PaintSeries),
  withPaintLineMeta(mrColor as PaintSeries),
  withPaintLineMeta(mrColorAqueous as PaintSeries),
  withPaintLineMeta(italeri as PaintSeries),
]


// Filter out hidden paint lines
const hiddenIds = new Set((paintLines as any[]).filter(pl => pl.hidden).map(pl => `${pl.manufacturer}|${pl.series}`))
export const allSeries: PaintSeries[] = configuredSeries.filter(series =>
  paintLineMetaByKey.has(`${series.manufacturer}|${series.series}`) &&
  !hiddenIds.has(`${series.manufacturer}|${series.series}`)
)

/** All unique manufacturer names (only visible paint lines) */
export const allManufacturers: string[] = [...new Set(allSeries.map(s => s.manufacturer))]
