'use client'

import { AlertTriangle } from 'lucide-react'

interface WarningBannerProps {
  warnings: string[]
}

export function WarningBanner({ warnings }: WarningBannerProps) {
  return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
      <div className="flex items-start space-x-3">
        <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-yellow-800 mb-2">⚠️ 风险提示</h3>
          <ul className="space-y-1">
            {warnings.map((warning, index) => (
              <li key={index} className="text-sm text-yellow-700">
                • {warning}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
