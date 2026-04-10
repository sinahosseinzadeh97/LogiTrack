import { motion } from 'framer-motion'
import { MapPin } from 'lucide-react'

export default function RegionsPage() {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: '1rem', textAlign: 'center' }}>
        <MapPin size={48} color="var(--accent-blue)" style={{ opacity: 0.5 }} />
        <h2 style={{ fontWeight: 700, fontSize: '1.1rem' }}>Brazil Choropleth Map</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', maxWidth: 380 }}>
          Interactive state-level delivery performance map using react-leaflet.<br />
          Full implementation pending GeoJSON region data integration in Phase 6.
        </p>
        <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
          {[['SP', 'var(--accent-green)'],['RJ','var(--accent-green)'],['MG','var(--warn)'],['RS','var(--accent-blue)'],['PR','var(--accent-green)']].map(([state, color]) => (
            <div key={state} style={{ padding: '0.875rem 1.5rem', background: 'var(--bg-surface2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', textAlign: 'center' }}>
              <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '1.25rem', fontWeight: 700, color }}>{state}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>demo</div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
