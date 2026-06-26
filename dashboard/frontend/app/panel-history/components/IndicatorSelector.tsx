'use client'

import { useMemo } from 'react'
import { X } from 'lucide-react'

interface IndicatorSelectorProps {
  catalog: any[]
  selected: string[]
  onChange: (selected: string[]) => void
}

export function IndicatorSelector({ catalog, selected, onChange }: IndicatorSelectorProps) {
  // Group indicators by category
  const groupedIndicators = useMemo(() => {
    const groups: Record<string, any[]> = {}
    catalog.forEach((item) => {
      const category = item.category || 'other'
      if (!groups[category]) {
        groups[category] = []
      }
      groups[category].push(item)
    })
    return groups
  }, [catalog])
  
  const categoryLabels: Record<string, string> = {
    growth: '增长',
    inflation: '通胀',
    liquidity: '流动性',
    rates: '利率',
    risk: '风险',
    inventory: '库存',
    other: '其他',
  }
  
  const handleToggle = (code: string) => {
    if (selected.includes(code)) {
      onChange(selected.filter((c) => c !== code))
    } else {
      onChange([...selected, code])
    }
  }
  
  return (
    <div className="space-y-2">
      <label className="text-sm text-muted-foreground">选择指标（可多选）:</label>
      
      <div className="flex flex-wrap gap-2">
        {selected.map((code) => {
          const item = catalog.find((c) => c.code === code)
          return (
            <span
              key={code}
              className="inline-flex items-center space-x-1 px-2 py-1 bg-primary text-primary-foreground rounded-md text-sm"
            >
              <span>{item?.name || code}</span>
              <button
                onClick={() => handleToggle(code)}
                className="hover:bg-primary-foreground/20 rounded"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          )
        })}
      </div>
      
      <div className="max-h-40 overflow-y-auto border rounded-md p-2 space-y-2">
        {Object.entries(groupedIndicators).map(([category, items]) => (
          <div key={category}>
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
              {categoryLabels[category] || category}
            </div>
            <div className="flex flex-wrap gap-1">
              {items.map((item) => (
                <button
                  key={item.code}
                  onClick={() => handleToggle(item.code)}
                  className={`px-2 py-1 text-xs rounded-md transition-colors ${
                    selected.includes(item.code)
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary hover:bg-secondary/80'
                  }`}
                >
                  {item.name}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
