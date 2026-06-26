'use client'

import { useState } from 'react'
import { useLatestState, useStateByDate, useStateHistory } from '@/hooks/useStates'
import { useNarrative } from '@/hooks/useAnalysis'
import { RegimeCard } from './components/RegimeCard'
import { DimensionCards } from './components/DimensionCards'
import { WarningBanner } from './components/WarningBanner'
import { FactorTable } from './components/FactorTable'
import { DateSelector } from './components/DateSelector'
import { formatMonth } from '@/lib/utils'

export default function PanelSnapshot() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  
  const { data: latestState, isLoading: latestLoading } = useLatestState()
  const { data: selectedState, isLoading: selectedLoading } = useStateByDate(selectedDate || '')
  const { data: history } = useStateHistory()
  
  const displayState = selectedDate ? selectedState : latestState
  const isLoading = selectedDate ? selectedLoading : latestLoading
  
  // Fetch narrative for the displayed date
  const { data: narrative, isLoading: narrativeLoading } = useNarrative(displayState?.date || '')
  
  const availableDates = history?.map((item: any) => item.date) || []
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-lg text-muted-foreground">加载中...</div>
      </div>
    )
  }
  
  if (!displayState) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-lg text-muted-foreground">暂无数据</div>
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">截面分析</h1>
          <p className="text-muted-foreground">
            查看特定月份的宏观状态截面及详细分析
          </p>
        </div>
        <DateSelector
          dates={availableDates}
          selectedDate={selectedDate}
          onSelect={setSelectedDate}
        />
      </div>
      
      {/* Regime Card */}
      <RegimeCard
        date={displayState.date}
        regime={displayState.regime}
        isLatest={!selectedDate}
      />
      
      {/* Dimension Cards */}
      <DimensionCards
        growth={displayState.growth}
        inflation={displayState.inflation}
        liquidity={displayState.liquidity}
      />
      
      {/* Warnings */}
      {displayState.warnings && displayState.warnings.length > 0 && (
        <WarningBanner warnings={displayState.warnings} />
      )}
      
      {/* Factor Table */}
      <FactorTable
        growth={displayState.growth}
        inflation={displayState.inflation}
        liquidity={displayState.liquidity}
      />
      
      {/* Narrative Analysis Section */}
      <div className="border-t pt-6 mt-6">
        <h2 className="text-xl font-bold mb-4">📋 分析报告</h2>
        
        {narrativeLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-muted-foreground">生成分析中...</div>
          </div>
        ) : narrative ? (
          <div className="space-y-6">
            {/* Overview */}
            <div className="bg-card rounded-lg border p-6">
              <h3 className="text-lg font-semibold mb-3">状态综述</h3>
              <p className="text-base leading-relaxed">{narrative.overview}</p>
            </div>
            
            {/* Dimension Details */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <DimensionDetailCard
                title="📈 增长维度解读"
                content={narrative.growth_detail}
                color="blue"
              />
              <DimensionDetailCard
                title="💰 通胀维度解读"
                content={narrative.inflation_detail}
                color="amber"
              />
              <DimensionDetailCard
                title="💧 流动性维度解读"
                content={narrative.liquidity_detail}
                color="purple"
              />
            </div>
            
            {/* Warnings */}
            {narrative.warnings && narrative.warnings.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h3 className="font-semibold text-yellow-800 mb-2">⚠️ 风险提示</h3>
                <ul className="space-y-1">
                  {narrative.warnings.map((warning: string, index: number) => (
                    <li key={index} className="text-sm text-yellow-700">
                      • {warning}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Strategy Implication */}
            {narrative.strategy_implication && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-green-800 mb-3">🎯 策略含义</h3>
                <div className="text-sm text-green-700 whitespace-pre-line">
                  {narrative.strategy_implication}
                </div>
              </div>
            )}
            
            {/* Historical Context */}
            {narrative.historical_context && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-blue-800 mb-3">📚 历史对比</h3>
                <p className="text-sm text-blue-700">{narrative.historical_context}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-32">
            <div className="text-muted-foreground">暂无分析数据</div>
          </div>
        )}
      </div>
    </div>
  )
}

function DimensionDetailCard({ title, content, color }: { title: string; content: string; color: string }) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-200',
    amber: 'bg-amber-50 border-amber-200',
    purple: 'bg-purple-50 border-purple-200',
  }
  
  return (
    <div className={`rounded-lg border p-4 ${colorClasses[color] || 'bg-muted'}`}>
      <h3 className="font-semibold mb-2">{title}</h3>
      <p className="text-sm leading-relaxed">{content || '暂无数据'}</p>
    </div>
  )
}
