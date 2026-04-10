import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Zap } from 'lucide-react'
import { alertsApi, PredictResponse } from '@/api/alerts'

const schema = z.object({
  distance_km:   z.number().min(1).max(10000),
  category_name: z.string().min(1, 'Required'),
  seller_state:  z.string().min(2).max(2),
  day_of_week:   z.number().min(0).max(6),
  freight_value: z.number().min(0),
  price:         z.number().min(0),
})

type FormValues = z.infer<typeof schema>

const CATEGORIES = [
  'beleza_saude', 'informatica_acessorios', 'automotivo', 'cama_mesa_banho',
  'moveis_decoracao', 'esporte_lazer', 'perfumaria', 'utilidades_domesticas',
  'telefonia', 'relogios_presentes', 'ferramentas_jardim', 'cool_stuff',
  'malas_acessorios', 'fraldas_higiene', 'fashion_bolsas_e_acessorios',
]
const BR_STATES = ['SP','RJ','MG','RS','PR','SC','BA','GO','PE','CE','ES','AM','DF']
const DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

function ProbGauge({ value }: { value: number }) {
  const pct = value * 100
  const color = value > 0.8 ? 'var(--danger)' : value > 0.65 ? 'var(--warn)' : 'var(--accent-green)'
  const r = 54, circ = 2 * Math.PI * r
  const offset = circ - (pct / 100) * circ

  return (
    <svg width={132} height={132} viewBox="0 0 132 132">
      <circle cx={66} cy={66} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={10} />
      <circle
        cx={66} cy={66} r={r} fill="none"
        stroke={color} strokeWidth={10}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        className="gauge-circle"
        style={{ transition: 'stroke-dashoffset 600ms ease, stroke 300ms ease' }}
      />
      <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle"
        fill={color} fontSize={22} fontWeight={700} fontFamily="JetBrains Mono, monospace">
        {pct.toFixed(0)}%
      </text>
    </svg>
  )
}

export function PredictForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { seller_state: 'SP', day_of_week: 1, distance_km: 500, freight_value: 20, price: 100 },
  })
  const [result, setResult] = useState<PredictResponse | null>(null)

  const { mutate, isPending, error } = useMutation({
    mutationFn: alertsApi.predict,
    onSuccess: setResult,
  })

  const onSubmit = (data: FormValues) => mutate(data)

  const fieldStyle = { display: 'flex', flexDirection: 'column' as const, gap: '0.3rem' }
  const labelStyle = { fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' as const, letterSpacing: '0.07em' }

  return (
    <div>
      <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
          <div style={fieldStyle}>
            <label style={labelStyle}>Distance (km)</label>
            <input className="input" type="number" {...register('distance_km', { valueAsNumber: true })} />
            {errors.distance_km && <span style={{ fontSize: '0.72rem', color: 'var(--danger)' }}>{errors.distance_km.message}</span>}
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Seller State</label>
            <select className="input" {...register('seller_state')}>
              {BR_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Category</label>
            <select className="input" {...register('category_name')}>
              <option value="">Select…</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
            </select>
            {errors.category_name && <span style={{ fontSize: '0.72rem', color: 'var(--danger)' }}>{errors.category_name.message}</span>}
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Day of Week</label>
            <select className="input" {...register('day_of_week', { valueAsNumber: true })}>
              {DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
            </select>
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Freight Value (R$)</label>
            <input className="input" type="number" step="0.01" {...register('freight_value', { valueAsNumber: true })} />
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Price (R$)</label>
            <input className="input" type="number" step="0.01" {...register('price', { valueAsNumber: true })} />
          </div>
        </div>

        <button className="btn btn-primary" type="submit" disabled={isPending} style={{ alignSelf: 'flex-start', gap: '0.5rem' }}>
          {isPending ? (
            <><span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.6s linear infinite' }} /> Predicting…</>
          ) : (
            <><Brain size={15} /> Predict Delay Risk</>
          )}
        </button>

        {error && (
          <div style={{ padding: '0.75rem', background: 'rgba(255,71,87,0.1)', border: '1px solid rgba(255,71,87,0.25)', borderRadius: 'var(--radius)', color: 'var(--danger)', fontSize: '0.85rem' }}>
            Prediction failed. Make sure a model is loaded on the backend.
          </div>
        )}
      </form>

      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35 }}
            style={{ marginTop: '1.5rem', padding: '1.5rem', background: 'var(--bg-surface2)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-lg)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <ProbGauge value={result.delay_probability} />
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.5rem' }}>
                  Prediction Result
                </div>
                <span className={`badge ${result.risk_level === 'high' ? 'badge-danger' : result.risk_level === 'medium' ? 'badge-warn' : 'badge-green'}`} style={{ fontSize: '0.85rem', padding: '0.35rem 0.875rem' }}>
                  <Zap size={12} /> {result.risk_level.toUpperCase()} RISK
                </span>
                <p style={{ marginTop: '0.75rem', fontSize: '0.83rem', color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 260 }}>
                  {result.risk_level === 'high'
                    ? 'This shipment has a high probability of delay. Consider proactive communication with the customer and investigate carrier options.'
                    : result.risk_level === 'medium'
                    ? 'Moderate delay risk detected. Monitor this shipment closely over the next 48 hours.'
                    : 'Low delay risk. This shipment is likely to be delivered on time.'}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
