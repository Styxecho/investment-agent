'use client'

import { useMemo } from 'react'
import { useIndicatorHistory } from '@/hooks/useIndicators'
import { PlotlyChart } from '@/components/shared/PlotlyChart'
import { formatDate } from '@/lib/utils'

interface SingleAxisChartProps {
  indicators: string[]
  startDate?: string
  endDate?: string
}

export function SingleAxisChart({ indicators, startDate, endDate }: SingleAxisChartProps) {
  const { data: rawData, isLoading } = useIndicatorHistory(
    indicators,
    startDate,
    endDate
  )

  const chartData = useMemo(() => {
    if (!rawData || rawData.length === 0) return []

    return rawData.map((indicator: any, index: number) => {
      const dates = indicator.data.map((d: any) => formatDate(d.date))
      const values = indicator.data.map((d: any) => d.value)

      return {
        x: dates,
        y: values,
        name: indicator.name,
        type: 'scatter',
        mode: 'lines+markers',
        line: {
          width: 2,
          color: getColor(index),
        },
        marker: {
          size: 4,
        },
      }
    })
  }, [rawData])

  const layout = useMemo(() => {
    return {
      title: {
        text: '原始值走势',
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
  }, [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[500px] bg-muted rounded-lg">
        <div className="text-muted-foreground">加载图表数据...</div>
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-[500px] bg-muted rounded-lg">
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

function getColor(index: number): string {
  const colors = [
    '#2563eb', '#dc2626', '#16a34a', '#ca8a04', '#9333ea', '#0891b2',
  ]
  return colors[index % colors.length]
}
