export const BR_STATES = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA',
  'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
] as const

/**
 * Tile-grid map of Brazil: each state's [column, row] on a 7-column grid, roughly
 * where it sits geographically. Reads like a map without needing GeoJSON.
 */
export const STATE_TILES: Record<string, [number, number]> = {
  RR: [2, 0], AP: [4, 0],
  AM: [1, 1], PA: [3, 1], MA: [4, 1], CE: [5, 1], RN: [6, 1],
  AC: [0, 2], RO: [1, 2], TO: [3, 2], PI: [4, 2], PE: [5, 2], PB: [6, 2],
  MT: [2, 3], GO: [3, 3], BA: [4, 3], SE: [5, 3], AL: [6, 3],
  MS: [2, 4], DF: [3, 4], MG: [4, 4], ES: [5, 4],
  SP: [3, 5], RJ: [4, 5],
  PR: [2, 6], SC: [3, 6], RS: [2, 7],
}
