'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { TrendingUp, BarChart3, BookOpen } from 'lucide-react'

const navItems = [
  { href: '/panel-history', label: '历史走势', icon: TrendingUp },
  { href: '/panel-snapshot', label: '截面分析', icon: BarChart3 },
  { href: '/panel-methodology', label: '方法论', icon: BookOpen },
]

export function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="bg-primary text-primary-foreground shadow-md">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link href="/" className="text-xl font-bold">
            📊 宏观状态分析
          </Link>
          
          <div className="flex space-x-1">
            {navItems.map((item) => {
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-md transition-colors ${
                    isActive
                      ? 'bg-primary-foreground/20'
                      : 'hover:bg-primary-foreground/10'
                  }`}
                >
                  <item.icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}
