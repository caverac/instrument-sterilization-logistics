import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from '@/components/Layout'
import { Backtest } from '@/routes/Backtest'
import { Calibration } from '@/routes/Calibration'
import { Explorer } from '@/routes/Explorer'
import { Model } from '@/routes/Model'

export const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/calibration" element={<Calibration />} />
          <Route path="/model" element={<Model />} />
        </Route>

        <Route path="/" element={<Navigate to="/explorer" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
