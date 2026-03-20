<template>
  <section class="section results-section">
    <div class="section-header">
      <h2>Conversion Results</h2>
    </div>

    <div class="results-table-wrapper">
      <table class="results-table">
        <thead>
          <tr>
            <th :class="['col-input', layoutClass]">
              <code>{{ inputSeriesName }}</code>
            </th>
            <th v-for="series in uniqueTargetSeries" :key="series" :class="['col-target', `col-target-${series}`, layoutClass]">
              {{ series }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(result, idx) in results" :key="idx" :class="{ 'row-no-match': result.correspondences.length === 0 }">
            <td :class="['col-input', layoutClass]">
              <div class="color-info">
                <div class="input-item">
                  <div class="color-code">
                    <code>{{ result.inputCode.toUpperCase() }}</code>
                  </div>
                  <div class="color-name">
                    <span v-if="result.sourceColor">
                      {{ result.sourceColor.name }}
                    </span>
                    <span v-else class="text-not-found">Not found</span>
                  </div>
                  <div
                    v-if="showRgbSwatches && result.sourceColor"
                    class="swatch-small"
                    :style="{ backgroundColor: result.sourceColor.rgb }"
                    :title="result.sourceColor.rgb"
                  ></div>
                </div>
              </div>
            </td>

            <!-- Target columns -->
            <td v-for="series in uniqueTargetSeries" :key="series" :class="['col-target', `col-target-${series}`, layoutClass]">
              <div v-if="getMatchesForSeries(result, series).length > 0" class="color-info">
                <div v-for="(match, midx) in getMatchesForSeries(result, series)" :key="midx" class="match-item">
                  <div :class="['color-code', { 'code-center': !showTargetDescription }]">
                    <code>{{ formatMatchId(match) }}</code>
                  </div>
                  <div v-if="showTargetDescription" class="color-name">{{ match.name }}</div>
                  <div v-if="showRgbSwatches" class="swatch-small" :style="{ backgroundColor: match.rgb }" :title="match.rgb"></div>
                </div>
              </div>
              <span v-else class="text-not-found">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConversionResult, MatchedCorrespondence } from '../types'
import { allSeries } from '../data/index'

interface Props {
  results: ConversionResult[]
  targetFilter?: string[]
  showRgbSwatches?: boolean
  showTargetDescription?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  targetFilter: () => [],
  showRgbSwatches: true,
  showTargetDescription: true,
})

const showRgbSwatches = computed(() => props.showRgbSwatches)
const showTargetDescription = computed(() => props.showTargetDescription)

const layoutClass = computed(() => {
  const hasVisualElements = showRgbSwatches.value || showTargetDescription.value
  return hasVisualElements ? 'layout-expanded' : 'layout-compact'
})

const uniqueTargetSeries = computed(() => {
  const targets = new Set<string>()
  for (const result of props.results) {
    for (const match of result.correspondences) {
      targets.add(match.series)
    }
  }
  return Array.from(targets).sort()
})

const matchCount = computed(() => {
  return props.results.reduce((sum, r) => sum + r.correspondences.length, 0)
})

const inputSeriesName = computed(() => {
  return props.results[0]?.sourceSeries?.series ?? 'Input / Origin Series'
})

function getMatchesForSeries(result: ConversionResult, series: string): MatchedCorrespondence[] {
  return result.correspondences.filter(m => m.series === series)
}

function getSeriesData(manufacturer: string, series: string) {
  return allSeries.find(s => s.manufacturer === manufacturer && s.series === series)
}

function formatMatchId(match: MatchedCorrespondence): string {
  const seriesData = getSeriesData(match.manufacturer, match.series)
  if (!seriesData || seriesData.prefixes.length === 0) {
    return match.id
  }
  
  // Check if the ID already has a prefix
  const hasPrefix = seriesData.prefixes.some(prefix => match.id.startsWith(prefix))
  
  // If no prefix, add the first (default) prefix
  if (!hasPrefix) {
    return seriesData.prefixes[0] + match.id
  }
  
  return match.id
}
</script>

<style scoped>
.results-section {
  margin-top: 2rem;
  background: white;
}

.results-table-wrapper {
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.results-table thead {
  background: #f5f5f5;
  border-bottom: 2px solid #e0e0e0;
}

.results-table th {
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  color: #333;
  white-space: nowrap;
}

.results-table td {
  padding: 1rem;
  border-bottom: 1px solid #e0e0e0;
  vertical-align: top;
}

.results-table tbody tr:hover {
  background: #fafafa;
}

.results-table tbody tr.row-no-match {
  background: #fff3f3;
}

.col-input {
  min-width: 180px;
}

.col-input.layout-compact {
  min-width: 120px;
}

.col-target {
  min-width: 180px;
}

.col-target.layout-compact {
  min-width: 100px;
}

.swatch {
  width: 50px;
  height: 40px;
  border: 1px solid #ccc;
  border-radius: 4px;
  display: inline-block;
}

.swatch-small {
  width: 30px;
  height: 25px;
  border: 1px solid #ccc;
  border-radius: 3px;
  display: inline-block;
  margin: 0.25rem 0;
}

.text-not-found {
  color: #999;
  font-style: italic;
}

code {
  background: #f0f0f0;
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.color-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.input-item {
  padding: 0.5rem;
  background: #f9f9f9;
  border-radius: 4px;
  border-left: 3px solid #2f9e44;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.match-item {
  padding: 0.5rem;
  background: #f9f9f9;
  border-radius: 4px;
  border-left: 3px solid #667eea;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.color-info > .match-item:not(:last-child) {
  margin-bottom: 0.25rem;
}

.color-code {
  flex: 0 0 auto;
}

.color-code code {
  background: white;
  font-weight: 500;
}

.color-code.code-center {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}

.color-name {
  flex: 1;
  color: #555;
  min-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .results-table {
    font-size: 0.8rem;
  }

  .results-table th,
  .results-table td {
    padding: 0.75rem 0.5rem;
  }

  .match-item {
    flex-wrap: wrap;
  }

  .color-name {
    min-width: 80px;
  }
}
</style>
