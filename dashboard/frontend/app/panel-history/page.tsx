'use client'

import { useState, useMemo } from 'react'
import { useIndicatorCatalog } from '@/hooks/useIndicators'
import { useStateHistory } from '@/hooks/useStates'
import { IndicatorSelector } from './components/IndicatorSelector'
import { DualAxisChart } from './components/DualAxisChart'
import { SingleAxisChart } from './components/SingleAxisChart'
import { CycleDecomposition } from './components/CycleDecomposition'
import { ZScoreTimeline } from './components/ZScoreTimeline'
import { RegimeBackground } from './components/RegimeBackground'

// 有因子值的指标列表
const FACTOR_INDICATORS = [
  'CN_PMI_MFG_M',
  'CN_PMI_SVC_M', 
  'CN_PMI_COMP_M',
  'CN_IAV_YOY_M',
  'CN_CCPI_YOY_M',
  'CN_PPI_YOY_M',
  'CN_M2_YOY_M',
  'CN_SFS_YOY_M',
]

const TIME_RANGES = [
  { label: '1年', value: '1y' },
  { label: '3年', value: '3y' },
  { label: '5年', value: '5y' },
  { label: '全部', value: 'all' },
]

export default function PanelHistory() {
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>(['CN_PMI_MFG_M'])
  const [timeRange, setTimeRange] = useState('all')
  const [chartMode, setChartMode] = useState<'dual' | 'single' | 'cycle' | 'zscore'>('dual')
  
  const { data: catalog, isLoading: catalogLoading } = useIndicatorCatalog()
  const { data: stateHistory } = useStateHistory()
  
  // Check if selected indicator has factor data
  const hasFactor = selectedIndicators.length > 0 && 
    FACTOR_INDICATORS.includes(selectedIndicators[0])
  
  // Adjust chart mode based on factor availability
  const effectiveChartMode = useMemo(() => {
    if (chartMode === 'dual' && !hasFactor) return 'single'
    if (chartMode === 'cycle' && !hasFactor) return 'single'
    if (chartMode === 'zscore' && !hasFactor) return 'single'
    return chartMode
  }, [chartMode, hasFactor])
  
  // Calculate date range
  const dateRange = useMemo(() => {
    if (timeRange === 'all' || !stateHistory?.length) {
      return { start: undefined, end: undefined }
    }
    
    const latest = stateHistory[stateHistory.length - 1]?.date
    if (!latest) return { start: undefined, end: undefined }
    
    const latestYear = parseInt(latest.slice(0, 4))
    const latestMonth = parseInt(latest.slice(4, 6))
    
    let startYear = latestYear
    let startMonth = latestMonth
    
    switch (timeRange) {
      case '1y':
        startMonth -= 12
        break
      case '3y':
        startYear -= 3
        break
      case '5y':
        startYear -= 5
        break
    }
    
    if (startMonth <= 0) {
      startYear -= 1
      startMonth += 12
    }
    
    const startDate = `${startYear}${String(startMonth).padStart(2, '0')}01`
    return { start: startDate, end: latest }
  }, [timeRange, stateHistory])
  
  if (catalogLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-lg text-muted-foreground">加载中...</div>
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">历史走势</h1>
        <p className="text-muted-foreground">
          查看原始值与因子值的历史走势，辅助周期判断
        </p>
        {!hasFactor && selectedIndicators.length > 0 && (
          <p className="text-sm text-yellow-600 mt-1">
            提示: {selectedIndicators[0]} 暂无因子值，仅显示原始值。有因子值的指标: PMI系列、工业增加值、CPI、PPI、M2、社融
          </p>
        )}
      </div>
      
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4 p-4 bg-muted rounded-lg">
        <div className="flex-1 min-w-[300px]">
          <IndicatorSelector
            catalog={catalog || []}
            selected={selectedIndicators}
            onChange={setSelectedIndicators}
          />
        </div>
        
        <div className="flex items-center space-x-2">
          <label className="text-sm text-muted-foreground">时间范围:</label>
          <div className="flex space-x-1">
            {TIME_RANGES.map((range) => (
              <button
                key={range.value}
                onClick={() => setTimeRange(range.value)}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  timeRange === range.value
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-background hover:bg-muted-foreground/10'
                }`}
              >
                {range.label}
              </button>
            ))}
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <label className="text-sm text-muted-foreground">图表模式:</label>
          <select
            value={effectiveChartMode}
            onChange={(e) => setChartMode(e.target.value as any)}
            className="bg-background border rounded-md px-3 py-1 text-sm"
          >
            {hasFactor ? (
              <>
                <option value="dual">双轴图(原始值+Z-score)</option>
                <option value="single">单轴图(仅原始值)</option>
                <option value="cycle">周期分解</option>
                <option value="zscore">Z-score时间线</option>
              </>
            ) : (
              <>
                <option value="single">单轴图(原始值)</option>
                <option value="dual" disabled>双轴图(无因子值)</option>
              </>
            )}
          </select>
        </div>
      </div>
      
      {/* Charts */}
      <div className="space-y-6">
        {effectiveChartMode === 'dual' && (
          <DualAxisChart
            indicators={selectedIndicators}
            startDate={dateRange.start}
            endDate={dateRange.end}
          />
        )}
        
        {effectiveChartMode === 'single' && (
          <SingleAxisChart
            indicators={selectedIndicators}
            startDate={dateRange.start}
            endDate={dateRange.end}
          />
        )}
        
        {effectiveChartMode === 'cycle' && selectedIndicators.map((code) => (
          <CycleDecomposition
            key={code}
            indicatorCode={code}
            startDate={dateRange.start}
            endDate={dateRange.end}
          />
        ))}
        
        {effectiveChartMode === 'zscore' && selectedIndicators.map((code) => (
          <ZScoreTimeline
            key={code}
            indicatorCode={code}
            startDate={dateRange.start}
            endDate={dateRange.end}
          />
        ))}
      </div>
      
      {/* Regime Background Legend */}
      <RegimeBackground />
    </div>
  )
}
