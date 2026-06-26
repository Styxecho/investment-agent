'use client'

import { useMemo } from 'react'
import { useFactorDecomposition } from '@/hooks/useIndicators'
import { PlotlyChart } from '@/components/shared/PlotlyChart'
import { formatDate } from '@/lib/utils'

interface CycleDecompositionProps {
  indicatorCode: string
  startDate?: string
  endDate?: string
}

export function CycleDecomposition({ indicatorCode, startDate, endDate }: CycleDecompositionProps) {
  const { data, isLoading } = useFactorDecomposition(indicatorCode, startDate, endDate)

  const chartData = useMemo(() => {
    if (!data?.data) return []

    const dates = data.data.map((d: any) => formatDate(d.date))

    return [
      {
        x: dates,
        y: data.data.map((d: any) => d.raw_value),
        name: '原始值',
        type: 'scatter',
        mode: 'lines',
        line: { width: 2, color: '#2563eb' },
      },
      {
        x: dates,
        y: data.data.map((d: any) => d.trend_value),
        name: '趋势项 (HP滤波)',
        type: 'scatter',
        mode: 'lines',
        line: { width: 2, color: '#dc2626', dash: 'dash' },
      },
      {
        x: dates,
        y: data.data.map((d: any) => d.cycle_value),
        name: '周期项',
        type: 'scatter',
        mode: 'lines',
        line: { width: 2, color: '#16a34a' },
        fill: 'tozeroy',
        fillcolor: 'rgba(22, 163, 74, 0.1)',
      },
    ]
  }, [data])

  const layout = useMemo(() => {
    return {
      title: {
        text: `${data?.name || indicatorCode} - 周期分解`,
        font: { size: 16 },
      },
      xaxis: {
        title: '日期',
        tickangle: -45,
      },
      yaxis: {
        title: '数值',
        showgrid: true,
      },
      legend: {
        orientation: 'h' as const,
        y: -0.2,
      },
      hovermode: 'x unified' as const,
      margin: {
        l: 60,
        r: 30,
        t: 50,
        b: 100,
      },
    }
  }, [data, indicatorCode])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[400px] bg-muted rounded-lg">
        <div className="text-muted-foreground">加载中...</div>
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-[400px] bg-muted rounded-lg">
        <div className="text-muted-foreground">暂无数据</div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border p-4">
      <PlotlyChart
        data={chartData}
        layout={layout}
        config={{ responsive: true, displayModeBar: false }}
      />
    </div>
  )
}
