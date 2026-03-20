import type { PaintSeries } from '../types.ts'
import vallejoModelColor from './vallejo-model-color.json'
import vallejoModelAir from './vallejo-model-air.json'
import akRealColors from './ak-real-colors.json'
import mrColor from './mr-color.json'
import tamiyaAcrylic from './tamiya-acrylic.json'

export const allSeries: PaintSeries[] = [
  vallejoModelColor as PaintSeries,
  vallejoModelAir as PaintSeries,
  akRealColors as PaintSeries,
  mrColor as PaintSeries,
  tamiyaAcrylic as PaintSeries,
]

/** All unique manufacturer names */
export const allManufacturers: string[] = [...new Set(allSeries.map(s => s.manufacturer))]
