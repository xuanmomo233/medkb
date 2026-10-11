export const pct = (r: number) => Math.round(r * 100)
export const toneOf = (r: number) => (r >= 0.75 ? 'good' : r >= 0.55 ? 'warn' : 'bad')
