<template>
  <div class="container">
    <header class="header">
      <h1>🎨 Paint Colors Converter</h1>
    </header>

    <main class="main">
      <!-- Input Section -->
      <section class="section">
        <div class="section-header">
          <h2>1. Paint Codes</h2>
          <!-- <p>One color per line. Auto-detected color series if prefix is included.</p> -->
        </div>

        <textarea
          v-model="inputText"
          class="input-textarea"
          placeholder="70.950&#10;71.126&#10;XF-1&#10;RC001"
        />

        <div class="detection-box" v-if="!ALLOW_MULTIPLE_SERIES">
          <div class="detection-status">
            <span v-if="detectedSeriesObject"
              ><strong>Detected:</strong> {{ detectedSeriesObject.series }}
              ({{ detectedSeriesObject.manufacturer }})
            </span>
            <span v-else class="text-muted">No series detected. Select manually below.</span>
          </div>
          <div v-if="multipleSeriesDetected" class="detection-warning">
            Warning: Multiple paint series were detected in the input. Auto-detection may be inaccurate.
          </div>
        </div>
      </section>

      <!-- Source Paint Line -->
      <section class="section">
        <div class="section-header">
          <h2>2. Source Paint Line</h2>
          <label class="checkbox">
            <input type="checkbox" v-model="autoDetectEnabled" />
            Auto-detect
          </label>
        </div>

        <div v-if="!autoDetectEnabled" class="select-grid">
          <div class="form-group">
            <label>Brand</label>
            <select v-model="selectedManufacturer">
              <option value="">-- Select Brand --</option>
              <option v-for="mfr in manufacturerList" :key="mfr" :value="mfr">
                {{ mfr }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>Paint Line</label>
            <select v-model="selectedSourceSeries">
              <option value="">-- Select Paint Line --</option>
              <option v-for="series in filteredSeries" :key="series.series" :value="series" >
                {{ series.series }}
              </option>
            </select>
          </div>
        </div>

        <div v-if="(selectedSourceSeries || (autoDetectEnabled && !ALLOW_MULTIPLE_SERIES)) && !ALLOW_MULTIPLE_SERIES" class="info-box">
          <strong>Source Paint Line:</strong>
          {{
            selectedSourceSeries?.series ||
            detectedPaintSeries?.series ||
            'Not selected'
          }}
        </div>
      </section>

      <!-- Target Paint Line(s) Section -->
      <section class="section">
        <div class="section-header">
          <h2>3. Target Paint Line(s)</h2>
        </div>

        <div class="type-filters">
          <label class="radio">
            <input type="radio" v-model="targetSelectionMode" value="all" @change="applyTargetSelectionMode" />
            All
          </label>
          <label class="radio">
            <input type="radio" v-model="targetSelectionMode" value="enamel" @change="applyTargetSelectionMode" />
            Enamels
          </label>
          <label class="radio">
            <input type="radio" v-model="targetSelectionMode" value="acrylic-water" @change="applyTargetSelectionMode" />
            Acrylic water
          </label>
          <label class="radio">
            <input type="radio" v-model="targetSelectionMode" value="acrylic-alcohol" @change="applyTargetSelectionMode" />
            Acrylic alcohol
          </label>
          <label class="radio">
            <input type="radio" v-model="targetSelectionMode" value="laquer" @change="applyTargetSelectionMode" />
            Laquers
          </label>
        </div>

        <div class="checkbox-list">
          <label v-for="mfr in manufacturerList" :key="mfr" class="checkbox">
            <input type="checkbox" :value="mfr" v-model="selectedTargetManufacturers" @change="onManualTargetCheckboxChange" />
            {{ mfr }}
          </label>
        </div>
      </section>

      <!-- Convert Button -->
      <div class="button-group">
        <button @click="performConversion" class="btn btn-primary" :disabled="!canConvert">
          Convert Colors
        </button>
      </div>

      <!-- Results Section -->
      <ConversionResults
        v-if="conversionResults.length > 0"
        :results="conversionResults"
        :target-filter="selectedTargetManufacturers"
        :show-rgb-swatches="SHOW_RGB_SWATCHES"
        :show-target-description="SHOW_TARGET_COLOR_DESCRIPTION"
        :allow-multiple-series="ALLOW_MULTIPLE_SERIES && autoDetectEnabled"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PaintSeries } from './types'
import { allSeries, allManufacturers } from './data/index'
import { autoDetectFromInput, detectSeries } from './composables/useColorDetection'
import { convertColors, convertColorsMultipleSeries } from './composables/useConversion'
import ConversionResults from './components/ConversionResults.vue'
import type { ConversionResult } from './types'

const SHOW_RGB_SWATCHES = false
const SHOW_TARGET_COLOR_DESCRIPTION = false
const ALLOW_MULTIPLE_SERIES = true

const inputText = ref('')
const autoDetectEnabled = ref(true)
const selectedManufacturer = ref('')
const selectedSourceSeries = ref<PaintSeries | null>(null)
const selectedTargetManufacturers = ref<string[]>([...allManufacturers])
const targetSelectionMode = ref<'all' | 'enamel' | 'acrylic-water' | 'acrylic-alcohol' | 'laquer'>('all')
const conversionResults = ref<ConversionResult[]>([])

const manufacturerList = computed(() => allManufacturers)

const manufacturersByType = computed<Record<string, string[]>>(() => {
  const grouped = new Map<string, Set<string>>()

  for (const series of allSeries) {
    const seriesType = series.type
    if (!seriesType) continue

    if (!grouped.has(seriesType)) {
      grouped.set(seriesType, new Set<string>())
    }

    grouped.get(seriesType)?.add(series.manufacturer)
  }

  const result: Record<string, string[]> = {}
  for (const [seriesType, manufacturers] of grouped.entries()) {
    result[seriesType] = [...manufacturers]
  }

  return result
})

function sanitizeInputCode(code: string): string {
  return code.replace(/\s+/g, '').trim()
}

const normalizedInputCodes = computed(() => {
  return inputText.value
    .split('\n')
    .map(sanitizeInputCode)
    .filter(code => code.length > 0)
})

const detectedPaintSeries = computed(() => {
  if (!autoDetectEnabled.value || !inputText.value.trim()) return null
  const detection = autoDetectFromInput(normalizedInputCodes.value.join('\n'))
  return detection.series
})

const detectedSeriesObject = computed(() => {
  if (!detectedPaintSeries.value) return null
  return {
    series: detectedPaintSeries.value.series,
    manufacturer: detectedPaintSeries.value.manufacturer,
  }
})

const multipleSeriesDetected = computed(() => {
  if (ALLOW_MULTIPLE_SERIES) return false // Hide warning when multiple series are allowed
  if (!autoDetectEnabled.value || !inputText.value.trim()) return false

  const lines = normalizedInputCodes.value

  const detectedSeriesNames = new Set(
    lines
      .map(line => detectSeries(line).series?.series)
      .filter((seriesName): seriesName is string => Boolean(seriesName)),
  )

  return detectedSeriesNames.size > 1
})

const filteredSeries = computed(() => {
  if (!selectedManufacturer.value) return allSeries
  return allSeries.filter(s => s.manufacturer === selectedManufacturer.value)
})

// Auto-select series if manufacturer has only 1 series
watch(selectedManufacturer, (newMfr) => {
  const seriesForMfr = allSeries.filter(s => s.manufacturer === newMfr)
  if (seriesForMfr.length === 1) {
    selectedSourceSeries.value = seriesForMfr[0]
  } else {
    selectedSourceSeries.value = null
  }
})

const canConvert = computed(() => {
  const codes = normalizedInputCodes.value
  if (codes.length === 0) return false

  if (ALLOW_MULTIPLE_SERIES && autoDetectEnabled.value) {
    // In multi-series mode with auto-detect, we just need codes
    return selectedTargetManufacturers.value.length > 0
  } else {
    // In single-series mode or manual selection, we need a selected source series
    const source = selectedSourceSeries.value || (autoDetectEnabled.value && detectedPaintSeries.value)
    if (!source) return false

    return selectedTargetManufacturers.value.length > 0
  }
})


function onManualTargetCheckboxChange() {
  // If manual selection doesn't match any preset, clear radio selection
  const presetModes: Array<'all' | 'enamel' | 'acrylic-water' | 'acrylic-alcohol' | 'laquer'> = [
    'all',
    'enamel',
    'acrylic-water',
    'acrylic-alcohol',
    'laquer',
  ]
  let matched = false
  for (const mode of presetModes) {
    const manufacturersForMode = mode === 'all' ? manufacturerList.value : manufacturersByType.value[mode] ?? []
    if (manufacturersMatch(selectedTargetManufacturers.value, manufacturersForMode)) {
      targetSelectionMode.value = mode
      matched = true
      break
    }
  }
  if (!matched) {
    targetSelectionMode.value = '' as any // No radio selected
  }
}

function applyTargetSelectionMode() {
  if (targetSelectionMode.value === 'all') {
    selectedTargetManufacturers.value = [...manufacturerList.value]
    return
  }
  selectedTargetManufacturers.value = [...(manufacturersByType.value[targetSelectionMode.value] ?? [])]
}

function normalizeManufacturers(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b))
}

function manufacturersMatch(left: string[], right: string[]): boolean {
  const leftNormalized = normalizeManufacturers(left)
  const rightNormalized = normalizeManufacturers(right)
  if (leftNormalized.length !== rightNormalized.length) return false
  return leftNormalized.every((value, index) => value === rightNormalized[index])
}

// No need to sync radio from checkboxes here; handled in onManualTargetCheckboxChange

function performConversion() {
  const codes = normalizedInputCodes.value

  if (!codes.length) return

  if (ALLOW_MULTIPLE_SERIES && autoDetectEnabled.value) {
    // Convert with automatic series detection per code (only if auto-detect is enabled)
    conversionResults.value = convertColorsMultipleSeries(codes, selectedTargetManufacturers.value)
  } else {
    // Convert with a single source series
    const sourceSeries = selectedSourceSeries.value || (autoDetectEnabled.value ? detectedPaintSeries.value : null)

    if (!sourceSeries) return

    // Convert with target filter
    conversionResults.value = convertColors(codes, sourceSeries, selectedTargetManufacturers.value)
  }
}
</script>

<style scoped>
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 3rem 2rem;
  text-align: center;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.header h1 {
  margin: 0 0 0.5rem 0;
  font-size: 2.5rem;
}

.header p {
  margin: 0;
  font-size: 1.1rem;
  opacity: 0.9;
}

.main {
  padding: 2rem;
  background: #f5f5f5;
  min-height: calc(100vh - 200px);
}

.section {
  background: white;
  padding: 2rem;
  margin-bottom: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.section-header {
  margin-bottom: 1.5rem;
}

.section-header h2 {
  margin: 0 0 0.5rem 0;
  color: #333;
  font-size: 1.3rem;
}

.section-header p {
  margin: 0;
  color: #666;
  font-size: 0.95rem;
}

.input-textarea {
  width: 100%;
  min-height: 120px;
  padding: 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  resize: vertical;
  transition: border-color 0.2s;
}

.input-textarea:focus {
  outline: none;
  border-color: #667eea;
}

.detection-box {
  margin-top: 1rem;
  padding: 1rem;
  background: #f9f9f9;
  border-left: 4px solid #667eea;
  border-radius: 4px;
}

.detection-status {
  font-size: 0.95rem;
  color: #333;
}

.detection-warning {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: #b26a00;
}

.text-muted {
  color: #999;
}

.select-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  margin-bottom: 0.5rem;
  color: #333;
  font-weight: 500;
  font-size: 0.95rem;
}

.form-group select {
  padding: 0.75rem;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-size: 0.95rem;
  transition: border-color 0.2s;
}

.form-group select:focus {
  outline: none;
  border-color: #667eea;
}

.checkbox {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 0.95rem;
  color: #333;
  margin-bottom: 0.75rem;
}

.checkbox input {
  margin-right: 0.75rem;
  cursor: pointer;
  width: 18px;
  height: 18px;
}

.checkbox-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.type-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
}

.radio {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 0.95rem;
  color: #333;
}

.radio input {
  margin-right: 0.5rem;
  cursor: pointer;
}

.checkbox-all {
  grid-column: 1 / -1;
  margin-bottom: 0;
}

.info-box {
  padding: 1rem;
  background: #e8f5e9;
  border-radius: 6px;
  color: #2e7d32;
  font-size: 0.95rem;
}

.button-group {
  display: flex;
  gap: 1rem;
  margin: 2rem 0;
}

.btn {
  padding: 0.75rem 2rem;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .header {
    padding: 2rem 1.5rem;
  }

  .header h1 {
    font-size: 1.8rem;
  }

  .main {
    padding: 1rem;
  }

  .section {
    padding: 1.5rem;
  }

  .select-grid {
    grid-template-columns: 1fr;
  }

  .checkbox-list {
    grid-template-columns: 1fr;
  }
}
</style>
