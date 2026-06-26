'use client'

import { useEffect, useRef } from 'react'

interface PlotlyChartProps {
  data: any[]
  layout?: any
  config?: any
  style?: React.CSSProperties
}

export function PlotlyChart({ data, layout, config, style }: PlotlyChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const plotlyRef = useRef<any>(null)

  useEffect(() => {
    let isMounted = true

    const renderChart = async () => {
      if (!chartRef.current) return

      try {
        const Plotly = await import('plotly.js-dist-min')
        if (!isMounted) return

        plotlyRef.current = Plotly

        await Plotly.newPlot(chartRef.current, data, layout, config)
      } catch (error) {
        console.error('Failed to load Plotly:', error)
      }
    }

    renderChart()

    return () => {
      isMounted = false
      if (chartRef.current && plotlyRef.current) {
        try {
          plotlyRef.current.purge(chartRef.current)
        } catch (e) {
          // Ignore purge errors
        }
      }
    }
  }, [data, layout, config])

  return (
    <div
      ref={chartRef}
      style={{
        width: '100%',
        height: '500px',
        ...style,
      }}
    />
  )
}
