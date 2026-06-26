'use client'

import { formatMonth, getRegimeColor } from '@/lib/utils'

interface RegimeCardProps {
  date: string
  regime: string
  isLatest?: boolean
}

export function RegimeCard({ date, regime, isLatest = false }: RegimeCardProps) {
  const color = getRegimeColor(regime)
  
  return (
    <div 
      className="rounded-lg p-6 text-white shadow-lg"
      style={{ backgroundColor: color }}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm opacity-90 mb-1">
            {isLatest ? '最新状态' : formatMonth(date)}
          </div>
          <h2 className="text-3xl font-bold">{regime}</h2>
        </div>
        <div className="text-right">
          <div className="text-4xl opacity-50">📊</div>
        </div>
      </div>
    </div>
  )
}
