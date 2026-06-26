'use client'

import { useEffect, useState } from 'react'

export function Footer() {
  const [dataStatus, setDataStatus] = useState({
    latestDate: '-',
    totalMonths: '-',
    version: 'V8',
  })

  useEffect(() => {
    // Fetch data status
    fetch('/api/v1/states/latest')
      .then(res => res.json())
      .then(data => {
        if (data) {
          setDataStatus({
            latestDate: data.date || '-',
            totalMonths: '135',
            version: data.methodology_version || 'V8',
          })
        }
      })
      .catch(() => {
        // Silently fail
      })
  }, [])

  return (
    <footer className="bg-muted text-muted-foreground py-4 mt-auto">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-4">
            <span>数据时效: {dataStatus.latestDate}</span>
            <span>|</span>
            <span>共{dataStatus.totalMonths}个月</span>
            <span>|</span>
            <span>版本: {dataStatus.version}</span>
          </div>
          <div>
            © 2026 Investment Agent
          </div>
        </div>
      </div>
    </footer>
  )
}
