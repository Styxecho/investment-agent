/**
 * Utility functions
 */

export function formatDate(dateStr: string): string {
  if (!dateStr || dateStr.length !== 8) return dateStr
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
}

export function formatMonth(dateStr: string): string {
  if (!dateStr || dateStr.length !== 8) return dateStr
  return `${dateStr.slice(0, 4)}年${dateStr.slice(4, 6)}月`
}

export function formatNumber(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined || isNaN(value)) return '-'
  return value.toFixed(decimals)
}

export function formatPercentage(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined || isNaN(value)) return '-'
  return `${(value * 100).toFixed(decimals)}%`
}

export function getRegimeColor(regime: string): string {
  const colorMap: Record<string, string> = {
    '完美扩张': '#22c55e',
    '强势复苏': '#16a34a',
    '弱复苏': '#4ade80',
    '宽衰退': '#f59e0b',
    '失速衰退': '#dc2626',
    '典型滞胀': '#ea580c',
    '极端滞胀': '#991b1b',
    '过热期': '#f97316',
    '类衰退过渡': '#fbbf24',
    '震荡/观望': '#6b7280',
  }
  return colorMap[regime] || '#6b7280'
}

export function getDirectionArrow(direction: string): string {
  const arrowMap: Record<string, string> = {
    '↑': '↑',
    '↓': '↓',
    '→': '→',
    '上行': '↑',
    '下行': '↓',
    '平稳': '→',
  }
  return arrowMap[direction] || direction
}

export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ')
}
