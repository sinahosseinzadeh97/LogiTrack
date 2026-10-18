import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion } from 'framer-motion'
import { Eye, EyeOff, Truck, Lock, Mail } from 'lucide-react'
import { AxiosError } from 'axios'
import { useAuthStore } from '@/stores/authStore'

// Set at build time for the public demo only; leave unset anywhere real.
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD
const DEMO_ROLES = ['viewer', 'analyst', 'admin'] as const

const schema = z.object({
  email:    z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
})
type FormValues = z.infer<typeof schema>

export default function LoginPage() {
  const [showPw, setShowPw] = useState(false)
  const [apiError, setApiError] = useState('')
  const navigate = useNavigate()
  const { login } = useAuthStore()

  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormValues) => {
    setApiError('')
    try {
      await login(data.email, data.password)
      navigate({ to: '/overview' })
    } catch (error) {
      const tooMany = error instanceof AxiosError && error.response?.status === 429
      setApiError(tooMany ? 'Too many attempts. Wait a minute and try again.' : 'Invalid email or password.')
    }
  }

  return (
    <div className="login-bg" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: '1rem' }}>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
        style={{ width: '100%', maxWidth: 400 }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            width: 52, height: 52, borderRadius: 14, margin: '0 auto 1rem',
            background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-green))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 32px rgba(61,127,255,0.35)',
          }}>
            <Truck size={24} color="#fff" strokeWidth={2.5} />
          </div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '0.25rem' }}>LogiTrack</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Delivery performance and late-delivery risk for 99k Olist orders
          </p>
        </div>

        {/* Card */}
        <div className="card" style={{ padding: '1.75rem' }}>
          <h2 style={{ fontWeight: 700, fontSize: '1.05rem', marginBottom: '1.5rem' }}>Sign in to your account</h2>

          <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Email */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Email Address
              </label>
              <div style={{ position: 'relative' }}>
                <Mail size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)', pointerEvents: 'none' }} />
                <input
                  className="input"
                  style={{ paddingLeft: '2.25rem' }}
                  type="email"
                  placeholder="you@company.com"
                  autoComplete="email"
                  {...register('email')}
                />
              </div>
              {errors.email && <span style={{ fontSize: '0.75rem', color: 'var(--danger)' }}>{errors.email.message}</span>}
            </div>

            {/* Password */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <Lock size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)', pointerEvents: 'none' }} />
                <input
                  className="input"
                  style={{ paddingLeft: '2.25rem', paddingRight: '2.5rem' }}
                  type={showPw ? 'text' : 'password'}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPw((p) => !p)}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: 0 }}
                >
                  {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {errors.password && <span style={{ fontSize: '0.75rem', color: 'var(--danger)' }}>{errors.password.message}</span>}
            </div>

            {/* API error */}
            {apiError && (
              <motion.div
                initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                style={{ padding: '0.625rem 0.875rem', background: 'rgba(255,71,87,0.1)', border: '1px solid rgba(255,71,87,0.25)', borderRadius: 'var(--radius)', fontSize: '0.82rem', color: 'var(--danger)' }}
              >
                {apiError}
              </motion.div>
            )}

            <button
              className="btn btn-primary"
              type="submit"
              disabled={isSubmitting}
              style={{ width: '100%', justifyContent: 'center', padding: '0.7rem', fontSize: '0.9rem', marginTop: '0.25rem' }}
            >
              {isSubmitting ? (
                <><span style={{ display: 'inline-block', width: 16, height: 16, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.6s linear infinite' }} /> Signing in…</>
              ) : 'Sign In'}
            </button>
          </form>
        </div>

        {DEMO_PASSWORD && (
          <div className="card" style={{ marginTop: '1rem', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <span className="text-muted" style={{ fontSize: '0.75rem' }}>Demo accounts — pick one to fill the form:</span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {DEMO_ROLES.map((role) => (
                <button key={role} type="button" className="btn btn-ghost btn-sm" onClick={() => {
                  setValue('email', `${role}@logitrack.dev`)
                  setValue('password', DEMO_PASSWORD)
                }}>{role}</button>
              ))}
            </div>
          </div>
        )}
      </motion.div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
