'use client'

import { useMemo } from 'react'
import { useFactorDecomposition } from '@/hooks/useIndicators'
import { PlotlyChart } from '@/components/shared/PlotlyChart'
import { formatDate } from '@/lib/utils'

interface ZScoreTimelineProps {
  indicatorCode: string
  startDate?: string
  endDate?: string
}

export function ZScoreTimeline({ indicatorCode, startDate, endDate }: ZScoreTimelineProps) {
  const { data, isLoading } = useFactorDecomposition(indicatorCode, startDate, endDate)

  const chartData = useMemo(() => {
    if (!data?.data) return []

    const dates = data.data.map((d: any) => formatDate(d.date))
    const zscores = data.data.map((d: any) => d.zscore)
    const thresholds = data.data.map((d: any) => d.threshold)

    const upperThreshold = thresholds.map((t: number) => t || 0)
    const lowerThreshold = thresholds.map((t: number) => -(t || 0))

    return [
      {
        x: dates,
        y: upperThreshold,
        name: '上阈值',
        type: 'scatter',
        mode: 'lines',
        line: { width: 1, color: 'rgba(0, 0, 0, 0.2)', dash: 'dot' },
        showlegend: true,
        hoverinfo: 'skip' as const,
      },
      {
        x: dates,
        y: lowerThreshold,
        name: '下阈值',
        type: 'scatter',
        mode: 'lines',
        line: { width: 1, color: 'rgba(0, 0, 0, 0.2)', dash: 'dot' },
        fill: 'tonexty',
        fillcolor: 'rgba(0, 0, 0, 0.05)',
        showlegend: true,
        hoverinfo: 'skip' as const,
      },
      {
        x: dates,
        y: zscores,
        name: 'Z-score',
        type: 'scatter',
        mode: 'lines+markers',
        line: { width: 2, color: '#2563eb' },
        marker: {
          size: 6,
          color: zscores.map((z: number) => {
            const t = thresholds[zscores.indexOf(z)] || 0
            if (z > t) return '#16a34a' // green - above threshold
            if (z < -t) return '#dc2626' // red - below threshold
            return '#2563eb' // blue - within threshold
          }),
        },
      },
    ]
  }, [data])

  const layout = useMemo(() => {
    return {
      title: {
        text: `${data?.name || indicatorCode} - Z-score 时间线`,
        font: { size: 16 },
      },
      xaxis: {
        title: '日期',
        tickangle: -45,
      },
      yaxis: {
        title: 'Z-score',
        showgrid: true,
        zeroline: true,
        zerolinecolor: '#999',
        zerolinewidth: 1,
      },
      shapes: [
        {
          type: 'line',
          x0: 0,
          x1: 1,
          xref: 'paper',
          y0: 0,
          y1: 0,
          line: {
            color: '#999',
            width: 1,
            dash: 'solid',
          },
        },
      ],
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
