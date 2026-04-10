import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { mlApi } from '@/api/ml'
import { alertsApi } from '@/api/alerts'
import { PredictForm } from '@/components/alerts/PredictForm'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { SkeletonChart } from '@/components/shared/SkeletonCard'

export default function PredictionPage() {
  const { data: fi, isLoading: fiLoading } = useQuery({
    queryKey: ['ml', 'feature-importance'],
    queryFn: mlApi.getFeatureImportance,
    staleTime: 10 * 60 * 1000,
  })
  const { data: modelInfo } = useQuery({
    queryKey: ['ml', 'model-info'],
    queryFn: mlApi.getModelInfo,
    staleTime: 10 * 60 * 1000,
  })

  const chartData = (fi ?? [])
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 10)
    .map((d) => ({ name: d.feature.replace(/_/g, ' '), value: +(d.importance * 100).toFixed(2) }))

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
      style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', alignItems: 'start' }}>

      {/* Left — Form */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="card">
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '1rem' }}>
            Live Delay Predictor
          </div>
          <PredictForm />
        </div>

        {/* Model info */}
        {modelInfo && (
          <div className="card" style={{ fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '0.25rem' }}>Model Info</div>
            {[
              ['Version',   modelInfo.model_version],
              ['Algorithm', modelInfo.algorithm],
              ['ROC-AUC',   modelInfo.roc_auc?.toFixed(4) ?? 'N/A'],
              ['Trained',   modelInfo.trained_at ? new Date(modelInfo.trained_at).toLocaleDateString() : '—'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.375rem 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{k}</span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>{v}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right — Feature importance */}
      <div className="card">
        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '1rem' }}>
          Feature Importance — Top 10
        </div>
        {fiLoading ? <SkeletonChart height={320} /> : (
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 8 }}>
              <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
              <YAxis dataKey="name" type="category" width={150} tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(v: any) => [`${(v as number).toFixed(2)}%`, 'Importance']}
                contentStyle={{ background: 'var(--bg-surface2)', border: '1px solid var(--border-strong)', borderRadius: 8, fontSize: '0.8rem' }}
                labelStyle={{ color: 'var(--text-primary)' }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={18} animationDuration={800}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={`hsl(${220 - i * 10}, 80%, ${60 - i * 2}%)`} fillOpacity={0.9} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </motion.div>
  )
}
