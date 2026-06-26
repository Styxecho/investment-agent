'use client'

import { getRegimeColor } from '@/lib/utils'

const REGIMES = [
  { name: '完美扩张', desc: '经济景气度高' },
  { name: '强势复苏', desc: '复苏加速' },
  { name: '弱复苏', desc: '复苏偏弱' },
  { name: '过热期', desc: '通胀压力显现' },
  { name: '宽衰退', desc: '衰退但流动性宽松' },
  { name: '失速衰退', desc: '衰退且流动性紧' },
  { name: '典型滞胀', desc: '停滞+通胀' },
  { name: '极端滞胀', desc: '最恶劣环境' },
  { name: '类衰退过渡', desc: '衰退边缘' },
  { name: '震荡/观望', desc: '信号混合' },
]

export function RegimeBackground() {
  return (
    <div className="bg-muted rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">象限说明</h3>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {REGIMES.map((regime) => (
          <div key={regime.name} className="flex items-center space-x-2">
            <div
              className="w-4 h-4 rounded"
              style={{ backgroundColor: getRegimeColor(regime.name) }}
            />
            <div className="text-xs">
              <div className="font-medium">{regime.name}</div>
              <div className="text-muted-foreground">{regime.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
