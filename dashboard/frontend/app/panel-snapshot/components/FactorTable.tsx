'use client'

import { formatNumber } from '@/lib/utils'

interface FactorTableProps {
  growth: any
  inflation: any
  liquidity: any
}

export function FactorTable({ growth, inflation, liquidity }: FactorTableProps) {
  const indicators = [
    {
      name: '制造业PMI',
      category: '增长',
      raw: growth?.raw_values?.pmi,
      zscore: growth?.factor_values?.pmi_z,
      level: growth?.level,
      direction: growth?.direction,
    },
    {
      name: '工业增加值',
      category: '增长',
      raw: growth?.raw_values?.iav,
      zscore: growth?.factor_values?.iav_z,
      level: growth?.level,
      direction: growth?.direction,
    },
    {
      name: '核心CPI',
      category: '通胀',
      raw: inflation?.raw_values?.ccpi,
      zscore: inflation?.factor_values?.ccpi_z,
      level: inflation?.level,
      direction: inflation?.direction,
    },
    {
      name: 'PPI',
      category: '通胀',
      raw: inflation?.raw_values?.ppi,
      zscore: inflation?.factor_values?.ppi_z,
      level: inflation?.level,
      direction: inflation?.direction,
    },
    {
      name: 'M2',
      category: '流动性',
      raw: liquidity?.raw_values?.m2,
      zscore: liquidity?.factor_values?.m2_z,
      level: liquidity?.level,
      direction: liquidity?.direction,
    },
    {
      name: '社融',
      category: '流动性',
      raw: liquidity?.raw_values?.sfs,
      zscore: liquidity?.factor_values?.sfs_z,
      level: liquidity?.level,
      direction: liquidity?.direction,
    },
  ]

  return (
    <div className="rounded-lg border bg-card">
      <div className="p-4 border-b">
        <h3 className="font-semibold">指标因子值明细</h3>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="text-left p-3 font-medium">指标</th>
              <th className="text-left p-3 font-medium">分类</th>
              <th className="text-right p-3 font-medium">原始值</th>
              <th className="text-right p-3 font-medium">Z-score</th>
              <th className="text-left p-3 font-medium">水平</th>
              <th className="text-left p-3 font-medium">方向</th>
            </tr>
          </thead>
          <tbody>
            {indicators.map((indicator, index) => (
              <tr key={index} className="border-b last:border-0 hover:bg-muted/30">
                <td className="p-3 font-medium">{indicator.name}</td>
                <td className="p-3">
                  <span className="inline-flex items-center rounded-full px-2 py-1 text-xs font-medium bg-secondary">
                    {indicator.category}
                  </span>
                </td>
                <td className="p-3 text-right">{formatNumber(indicator.raw)}</td>
                <td className="p-3 text-right">{formatNumber(indicator.zscore)}</td>
                <td className="p-3">{indicator.level}</td>
                <td className="p-3">{indicator.direction}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
