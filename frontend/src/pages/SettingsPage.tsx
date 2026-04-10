import { motion } from 'framer-motion'
import { useSettingsStore } from '@/stores/settingsStore'
import { Sun, Moon } from 'lucide-react'

export default function SettingsPage() {
  const { theme, setTheme, alertRefreshInterval, setAlertRefreshInterval } = useSettingsStore()

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', maxWidth: 600 }}>

      <div className="card">
        <h2 style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: '1.25rem' }}>Appearance</h2>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 0', borderBottom: '1px solid var(--border)' }}>
          <div>
            <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>Color Theme</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Choose between dark and light mode</div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {(['dark', 'light'] as const).map((t) => (
              <button key={t} className={`btn ${theme === t ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setTheme(t)}>
                {t === 'dark' ? <><Moon size={14} /> Dark</> : <><Sun size={14} /> Light</>}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <h2 style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: '1.25rem' }}>Data & Refresh</h2>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 0', borderBottom: '1px solid var(--border)' }}>
          <div>
            <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>Alert Refresh Interval</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>How often to poll for new flagged shipments</div>
          </div>
          <select className="input" style={{ width: 140 }} value={alertRefreshInterval}
            onChange={(e) => setAlertRefreshInterval(Number(e.target.value))}>
            <option value={15}>15 seconds</option>
            <option value={30}>30 seconds</option>
            <option value={60}>1 minute</option>
            <option value={300}>5 minutes</option>
          </select>
        </div>
      </div>

      <div className="card">
        <h2 style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.5rem' }}>About</h2>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          LogiTrack v5.0 — Logistics KPI &amp; Delay Prediction Dashboard<br />
          Built with React 18 + TypeScript + Vite + TanStack Query + Framer Motion<br />
          Backend: FastAPI + PostgreSQL + XGBoost
        </p>
      </div>
    </motion.div>
  )
}
