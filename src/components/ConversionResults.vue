<template>
  <section class="section results-section">
    <div class="section-header">
      <h2>Conversion Results</h2>
    </div>

    <div class="results-table-wrapper">
      <table class="results-table">
        <thead>
          <tr>
            <th class="col-input">Input Code</th>
            <th class="col-source-name">Source Color</th>
            <th class="col-swatch">RGB Swatch</th>
            <th v-for="manufacturer in uniqueTargets" :key="manufacturer" :class="`col-target col-target-${manufacturer}`">
              {{ manufacturer }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(result, idx) in results" :key="idx" :class="{ 'row-no-match': result.correspondences.length === 0 }">
            <td class="col-input">
              <code>{{ result.inputCode }}</code>
            </td>

            <td class="col-source-name">
              <span v-if="result.sourceColor">
                {{ result.sourceColor.name }}
              </span>
              <span v-else class="text-not-found">Not found</span>
            </td>

            <td class="col-swatch">
              <div v-if="result.sourceColor" class="swatch" :style="{ backgroundColor: result.sourceColor.rgb }" :title="result.sourceColor.rgb"></div>
              <span v-else class="text-not-found">—</span>
            </td>

            <!-- Target columns -->
            <td v-for="manufacturer in uniqueTargets" :key="manufacturer" :class="`col-target col-target-${manufacturer}`">
              <div v-if="getMatchesForManufacturer(result, manufacturer).length > 0" class="target-matches">
                <div v-for="(match, midx) in getMatchesForManufacturer(result, manufacturer)" :key="midx" class="match-item">
                  <div class="match-code">
                    <code>{{ match.id }}</code>
                  </div>
                  <div class="match-name">{{ match.name }}</div>
                  <div class="swatch-small" :style="{ backgroundColor: match.rgb }" :title="match.rgb"></div>
                  <span v-if="match.source === 'reverse'" class="badge badge-reverse">reverse</span>
                </div>
              </div>
              <span v-else class="text-not-found">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="results-summary">
      <p><strong>{{ matchCount }}</strong> matches found across <strong>{{ uniqueTargets.length }}</strong> target manufacturers</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConversionResult, MatchedCorrespondence } from '../types'

interface Props {
  results: ConversionResult[]
  targetFilter?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  targetFilter: () => [],
})

const uniqueTargets = computed(() => {
  const targets = new Set<string>()
  for (const result of props.results) {
    for (const match of result.correspondences) {
      targets.add(match.manufacturer)
    }
  }
  return Array.from(targets).sort()
})

const matchCount = computed(() => {
  return props.results.reduce((sum, r) => sum + r.correspondences.length, 0)
})

function getMatchesForManufacturer(result: ConversionResult, manufacturer: string): MatchedCorrespondence[] {
  return result.correspondences.filter(m => m.manufacturer === manufacturer)
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
  min-width: 100px;
  font-family: monospace;
  font-weight: 500;
}

.col-source-name {
  min-width: 150px;
  color: #555;
}

.col-swatch {
  width: 60px;
}

.col-target {
  min-width: 180px;
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

.target-matches {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
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

.match-code {
  flex: 0 0 auto;
}

.match-code code {
  background: white;
  font-weight: 500;
}

.match-name {
  flex: 1;
  color: #555;
  min-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  background: #fff3cd;
  color: #856404;
  border-radius: 3px;
  font-size: 0.75rem;
  font-weight: 500;
  white-space: nowrap;
  flex: 0 0 auto;
}

.badge-reverse {
  background: #e7d4f5;
  color: #6f42c1;
}

.results-summary {
  padding: 1.5rem;
  background: #f9f9f9;
  border-top: 1px solid #e0e0e0;
  text-align: center;
  color: #666;
}

.results-summary p {
  margin: 0;
}

.results-summary strong {
  color: #333;
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

  .match-name {
    min-width: 80px;
  }
}
</style>
