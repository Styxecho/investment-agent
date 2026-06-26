'use client'

import { TrendingUp, DollarSign, Droplets, ArrowUp, ArrowDown, Minus } from 'lucide-react'
import { formatNumber, getDirectionArrow } from '@/lib/utils'

interface DimensionCardsProps {
  growth: any
  inflation: any
  liquidity: any
}

export function DimensionCards({ growth, inflation, liquidity }: DimensionCardsProps) {
  const dimensions = [
    {
      key: 'growth',
      title: '增长维度',
      icon: TrendingUp,
      color: 'bg-blue-50 border-blue-200',
      textColor: 'text-blue-900',
      state: growth,
      metrics: [
        { label: 'PMI', value: growth?.raw_values?.pmi, unit: '' },
        { label: '工业增加值', value: growth?.raw_values?.iav, unit: '%' },
      ],
    },
    {
      key: 'inflation',
      title: '通胀维度',
      icon: DollarSign,
      color: 'bg-amber-50 border-amber-200',
      textColor: 'text-amber-900',
      state: inflation,
      metrics: [
        { label: '核心CPI', value: inflation?.raw_values?.ccpi, unit: '%' },
        { label: 'PPI', value: inflation?.raw_values?.ppi, unit: '%' },
      ],
    },
    {
      key: 'liquidity',
      title: '流动性维度',
      icon: Droplets,
      color: 'bg-purple-50 border-purple-200',
      textColor: 'text-purple-900',
      state: liquidity,
      metrics: [
        { label: 'M2同比', value: liquidity?.raw_values?.m2, unit: '%' },
        { label: '社融同比', value: liquidity?.raw_values?.sfs, unit: '%' },
      ],
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {dimensions.map((dim) => (
        <div
          key={dim.key}
          className={`rounded-lg border p-4 ${dim.color}`}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <dim.icon className={`w-5 h-5 ${dim.textColor}`} />
              <span className={`font-semibold ${dim.textColor}`}>{dim.title}</span>
            </div>
            <div className="flex items-center space-x-1">
              <span className={`text-lg font-bold ${dim.textColor}`}>
                {dim.state?.level}
              </span>
              <span className={`text-lg ${dim.textColor}`}>
                {getDirectionArrow(dim.state?.direction)}
              </span>
            </div>
          </div>
          
          <div className="text-sm text-muted-foreground mb-3">
            {dim.state?.state}
          </div>
          
          <div className="space-y-2">
            {dim.metrics.map((metric) => (
              <div key={metric.label} className="flex justify-between text-sm">
                <span className="text-muted-foreground">{metric.label}</span>
                <span className="font-medium">
                  {formatNumber(metric.value)}{metric.unit}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
