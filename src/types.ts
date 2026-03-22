export interface Correspondence {
  manufacturer: string
  series: string
  id: string
  note?: string
}

export interface PaintColor {
  id: string
  name: string
  rgb: string
  correspondences: Correspondence[]
}

export interface PaintSeries {
  series: string
  manufacturer: string
  type?: string
  prefixes: string[]
  default_prefix?: string
  suffixes?: string[]
  default_suffix?: string
  colors: PaintColor[]
}

export interface MatchedCorrespondence {
  manufacturer: string
  series: string
  id: string
  name: string
  rgb: string
  note?: string
  source: 'direct' | 'reverse'
}

export interface ConversionResult {
  inputCode: string
  normalizedId: string
  sourceColor: PaintColor | null
  sourceSeries: PaintSeries | null
  correspondences: MatchedCorrespondence[]
}

export interface DetectionResult {
  series: PaintSeries | null
  confidence: 'certain' | 'possible' | 'unknown'
  matchingPrefix: string
}
