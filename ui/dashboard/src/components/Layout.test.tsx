import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { Layout } from './Layout'

const renderLayout = (initialPath = '/explorer') =>
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Layout />
    </MemoryRouter>
  )

describe('Layout', () => {
  it('renders the application title', () => {
    renderLayout()
    expect(screen.getByText('ISL Routing')).toBeInTheDocument()
  })

  it('renders all four primary nav items', () => {
    renderLayout()
    for (const label of ['Explorer', 'Backtest', 'Calibration', 'Model']) {
      expect(screen.getByRole('link', { name: new RegExp(label, 'i') })).toBeInTheDocument()
    }
  })

  it('marks the route that matches the URL as active', () => {
    renderLayout('/backtest')
    const active = screen.getByRole('link', { name: /backtest/i })
    expect(active.className).toContain('text-primary')
  })
})
