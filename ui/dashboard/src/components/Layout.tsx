import { Activity, Database, GitCompareArrows, LineChart, Microscope, Sliders } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

import { cn } from '@/lib/utils'

const navItems = [
  { to: '/explorer', icon: Sliders, label: 'Explorer' },
  { to: '/operations', icon: Database, label: 'Operations' },
  { to: '/backtest', icon: GitCompareArrows, label: 'Backtest' },
  { to: '/calibration', icon: LineChart, label: 'Calibration' },
  { to: '/model', icon: Microscope, label: 'Model' }
]

export function Layout() {
  return (
    <div className="flex h-screen bg-background">
      <aside className="w-64 border-r border-border bg-card">
        <div className="flex h-16 items-center gap-2 border-b border-border px-6">
          <Activity className="h-6 w-6 text-primary" />
          <span className="text-lg font-semibold">ISL Routing</span>
        </div>

        <nav className="flex flex-col gap-1 p-4">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                )
              }
            >
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
