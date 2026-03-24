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


function makePaintSeries(id: string, colors: any[]): PaintSeries {
  const meta = paintLineMetaByKey.get(id)
  if (!meta) {
    throw new Error(`Missing paint line metadata for id: ${id}`)
  }
  return {
    series: meta.series,
    manufacturer: meta.manufacturer,
    type: meta.type,
    prefixes: meta.prefixes ?? [],
    default_prefix: meta.default_prefix,
    suffixes: meta.suffixes ?? [],
    default_suffix: meta.default_suffix,
    colors: colors as any, // PaintColor[]
  }
}

const configuredSeries: PaintSeries[] = [
  makePaintSeries('vallejo-model-color', vallejoModelColor),
  makePaintSeries('vallejo-model-air', vallejoModelAir),
  makePaintSeries('ak-acrylic', akAcrylic),
  makePaintSeries('ak-real-colors', akRealColors),
  makePaintSeries('ammo-mig', ammoMig),
  makePaintSeries('ammo-mig-atom', ammoMigAtom),
  makePaintSeries('humbrol-enamel', humbrolEnamel),
  makePaintSeries('revell-acrylic', revellAcrylic),
  makePaintSeries('revell-enamel', revellEnamel),
  makePaintSeries('federal-standard', federalStandard),
  makePaintSeries('british-standard', britishStandard),
  makePaintSeries('ana-standard', anaStandard),
  makePaintSeries('rlm', rlm),
  makePaintSeries('mr-color', mrColor),
  makePaintSeries('mr-color-aqueous', mrColorAqueous),
  makePaintSeries('italeri', italeri),
]


// Filter out hidden paint lines
const hiddenIds = new Set((paintLines as any[]).filter(pl => pl.hidden).map(pl => pl.id))
export const allSeries: PaintSeries[] = configuredSeries.filter(series => {
  const meta = (paintLines as any[]).find(pl => pl.series === series.series && pl.manufacturer === series.manufacturer)
  return meta && meta.id && paintLineMetaByKey.has(meta.id) && !hiddenIds.has(meta.id)
})

/** All unique manufacturer names (only visible paint lines) */
export const allManufacturers: string[] = [...new Set(allSeries.map(s => s.manufacturer))]
