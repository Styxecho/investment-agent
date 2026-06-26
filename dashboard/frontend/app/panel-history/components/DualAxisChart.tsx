'use client'

import { useMemo } from 'react'
import { useIndicatorHistory } from '@/hooks/useIndicators'
import { useFactorDecomposition } from '@/hooks/useIndicators'
import { PlotlyChart } from '@/components/shared/PlotlyChart'
import { formatDate } from '@/lib/utils'

interface DualAxisChartProps {
  indicators: string[]
  startDate?: string
  endDate?: string
}

export function DualAxisChart({ indicators, startDate, endDate }: DualAxisChartProps) {
  // Fetch raw data for all selected indicators
  const { data: rawData, isLoading: rawLoading } = useIndicatorHistory(
    indicators,
    startDate,
    endDate
  )

  // Fetch factor data for the first indicator (for Z-score on right axis)
  const { data: factorData, isLoading: factorLoading } = useFactorDecomposition(
    indicators[0],
    startDate,
    endDate
  )

  const isLoading = rawLoading || factorLoading

  const chartData = useMemo(() => {
    if (!rawData || rawData.length === 0) return []

    const traces: any[] = []

    // Add raw value traces (left axis)
    rawData.forEach((indicator: any, index: number) => {
      const dates = indicator.data.map((d: any) => formatDate(d.date))
      const values = indicator.data.map((d: any) => d.value)

      traces.push({
        x: dates,
        y: values,
        name: `${indicator.name} (原始值)`,
        type: 'scatter',
        mode: 'lines+markers',
        yaxis: 'y1',
        line: {
          width: 2,
          color: getColor(index),
        },
        marker: {
          size: 4,
        },
      })
    })

    // Add Z-score trace for first indicator (right axis)
    if (factorData?.data) {
      const dates = factorData.data.map((d: any) => formatDate(d.date))
      const zscores = factorData.data.map((d: any) => d.zscore)

      traces.push({
        x: dates,
        y: zscores,
        name: `${factorData.name} (Z-score)`,
        type: 'scatter',
        mode: 'lines',
        yaxis: 'y2',
        line: {
          width: 2,
          dash: 'dash',
          color: '#666',
        },
      })
    }

    return traces
  }, [rawData, factorData])

  const layout = useMemo(() => {
    return {
      title: {
        text: '原始值与因子值走势',
        font: {
          size: 16,
        },
      },
      xaxis: {
        title: '日期',
        tickangle: -45,
      },
      yaxis: {
        title: '原始值',
        side: 'left',
        showgrid: true,
      },
      yaxis2: {
        title: 'Z-score',
        side: 'right',
        overlaying: 'y',
        showgrid: false,
        zeroline: true,
        zerolinecolor: '#999',
        zerolinewidth: 1,
      },
      legend: {
        orientation: 'h' as const,
        y: -0.2,
      },
      hovermode: 'x unified' as const,
      margin: {
        l: 60,
        r: 60,
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
    '#2563eb', // blue
    '#dc2626', // red
    '#16a34a', // green
    '#ca8a04', // yellow
    '#9333ea', // purple
    '#0891b2', // cyan
  ]
  return colors[index % colors.length]
}
