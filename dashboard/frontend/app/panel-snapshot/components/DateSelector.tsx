'use client'

import { formatMonth } from '@/lib/utils'
import { ChevronDown } from 'lucide-react'

interface DateSelectorProps {
  dates: string[]
  selectedDate: string | null
  onSelect: (date: string | null) => void
}

export function DateSelector({ dates, selectedDate, onSelect }: DateSelectorProps) {
  // Sort dates in descending order
  const sortedDates = [...dates].sort((a, b) => b.localeCompare(a))
  
  return (
    <div className="flex items-center space-x-2">
      <label className="text-sm text-muted-foreground">选择月份:</label>
      <div className="relative">
        <select
          value={selectedDate || ''}
          onChange={(e) => onSelect(e.target.value || null)}
          className="appearance-none bg-background border rounded-md px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">最新</option>
          {sortedDates.map((date) => (
            <option key={date} value={date}>
              {formatMonth(date)}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
      </div>
    </div>
  )
}
