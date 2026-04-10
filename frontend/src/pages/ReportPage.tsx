import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText,
  Download,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Calendar,
  HardDrive,
  Play,
  ChevronRight,
  Eye,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportsApi, type Report } from '@/api/reports'
import { useAuthStore } from '@/stores/authStore'

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number | null): string {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Next Monday 09:00 UTC from today */
function nextScheduledRun(): string {
  const now = new Date()
  const dayOfWeek = now.getUTCDay() // 0=Sun, 1=Mon … 6=Sat
  const daysUntilMonday = dayOfWeek === 1 ? 7 : (8 - dayOfWeek) % 7 || 7
  const next = new Date(now)
  next.setUTCDate(now.getUTCDate() + daysUntilMonday)
  next.setUTCHours(9, 0, 0, 0)
  return next.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
    timeZone: 'UTC',
  })
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Report['status'] }) {
  const map = {
    pending: {
      icon: <Loader2 size={11} className="spin" />,
      label: 'Pending',
      color: 'var(--accent-yellow, #f59e0b)',
      bg: 'rgba(245,158,11,0.12)',
    },
    success: {
      icon: <CheckCircle2 size={11} />,
      label: 'Ready',
      color: 'var(--accent-green, #22c55e)',
      bg: 'rgba(34,197,94,0.12)',
    },
    failed: {
      icon: <XCircle size={11} />,
      label: 'Failed',
      color: 'var(--accent-red, #ef4444)',
      bg: 'rgba(239,68,68,0.12)',
    },
  }
  const s = map[status]
  return (
    <span
      id={`status-badge-${status}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        fontSize: '0.72rem',
        fontWeight: 600,
        color: s.color,
        background: s.bg,
        borderRadius: '999px',
        padding: '2px 8px',
        letterSpacing: '0.02em',
      }}
    >
      {s.icon}
      {s.label}
    </span>
  )
}

// ── Preview modal ─────────────────────────────────────────────────────────────

function PreviewModal({
  reportId,
  onClose,
}: {
  reportId: number
  onClose: () => void
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['report-preview', reportId],
    queryFn: () => reportsApi.preview(reportId),
  })

  return (
    <div
      id="preview-modal-overlay"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.72)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        backdropFilter: 'blur(4px)',
        padding: '24px',
      }}
    >
      <motion.div
        initial={{ scale: 0.92, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.92, opacity: 0 }}
        transition={{ duration: 0.22 }}
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--surface)',
          borderRadius: '16px',
          border: '1px solid var(--border)',
          padding: '24px',
          maxWidth: '900px',
          width: '100%',
          maxHeight: '85vh',
          overflowY: 'auto',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontWeight: 700, fontSize: '1rem' }}>Report Preview</h2>
          <button id="preview-close-btn" className="btn btn-ghost" onClick={onClose} style={{ padding: '6px 12px' }}>
            Close
          </button>
        </div>
        {isLoading && (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
            <Loader2 size={28} className="spin" style={{ margin: '0 auto 8px', display: 'block' }} />
            Generating thumbnails…
          </div>
        )}
        {isError && (
          <p style={{ color: 'var(--accent-red, #ef4444)', textAlign: 'center', padding: '40px' }}>
            Preview unavailable (poppler/pdf2image may not be installed on the server).
          </p>
        )}
        {data && (
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
            {data.pages.map((b64, i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <img
                  src={`data:image/png;base64,${b64}`}
                  alt={`Page ${i + 1}`}
                  style={{
                    maxWidth: '260px',
                    borderRadius: '8px',
                    border: '1px solid var(--border)',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  }}
                />
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                  Page {i + 1}
                </p>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  )
}

// ── Report row ────────────────────────────────────────────────────────────────

function ReportRow({
  report,
  index,
  onPreview,
}: {
  report: Report
  index: number
  onPreview: (id: number) => void
}) {
  const handleDownload = async () => {
    const token = useAuthStore.getState().access_token
    const url = `${import.meta.env.VITE_API_URL ?? 'http://localhost:8001'}/api/v1/reports/${report.id}/download`
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) {
      console.error('Download failed:', response.status, response.statusText)
      return
    }
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = `logitrack-report-${report.id}.pdf`
    a.click()
    URL.revokeObjectURL(objectUrl)
  }

  return (
    <motion.tr
      id={`report-row-${report.id}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      style={{
        borderBottom: '1px solid var(--border)',
        transition: 'background 0.15s',
      }}
      className="table-row-hover"
    >
      <td style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileText size={14} color="var(--accent-blue)" />
          <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>
            {report.week}
          </span>
        </div>
      </td>
      <td style={{ padding: '12px 16px', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
        {formatDate(report.generated_at)}
      </td>
      <td style={{ padding: '12px 16px' }}>
        <StatusBadge status={report.status} />
      </td>
      <td style={{ padding: '12px 16px', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <HardDrive size={12} />
          {formatBytes(report.file_size_bytes)}
        </div>
      </td>
      <td style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {report.status === 'success' && (
            <>
              <button
                id={`download-btn-${report.id}`}
                className="btn btn-ghost"
                onClick={handleDownload}
                title="Download PDF"
                style={{ padding: '5px 10px', fontSize: '0.75rem', gap: '4px' }}
              >
                <Download size={12} />
                Download
              </button>
              <button
                id={`preview-btn-${report.id}`}
                className="btn btn-ghost"
                onClick={() => onPreview(report.id)}
                title="Preview pages"
                style={{ padding: '5px 10px', fontSize: '0.75rem', gap: '4px' }}
              >
                <Eye size={12} />
                Preview
              </button>
            </>
          )}
          {report.status === 'pending' && (
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Generating…</span>
          )}
          {report.status === 'failed' && (
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-red, #ef4444)' }}>
              Generation failed
            </span>
          )}
        </div>
      </td>
    </motion.tr>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ReportPage() {
  const qc = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const canGenerate = user?.role === 'analyst' || user?.role === 'admin'
  const [previewId, setPreviewId] = useState<number | null>(null)

  const {
    data: reports,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['reports'],
    queryFn: reportsApi.list,
    refetchInterval: 15_000, // poll every 15 s to catch pending → success
  })

  const generateMutation = useMutation({
    mutationFn: reportsApi.generate,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['reports'] })
    },
  })

  const hasReports = reports && reports.length > 0

  return (
    <motion.div
      id="reports-page"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}
    >
      {/* ── Page header ────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontWeight: 800, fontSize: '1.4rem', letterSpacing: '-0.02em', margin: 0 }}>
            PDF Reports
          </h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Automated weekly performance summaries
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            id="refresh-reports-btn"
            className="btn btn-ghost"
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh list"
            style={{ gap: '6px' }}
          >
            <RefreshCw size={14} className={isFetching ? 'spin' : ''} />
            Refresh
          </button>
          {canGenerate && (
            <button
              id="generate-report-btn"
              className="btn btn-primary"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
              style={{ gap: '6px' }}
            >
              {generateMutation.isPending ? (
                <Loader2 size={14} className="spin" />
              ) : (
                <Play size={14} />
              )}
              Generate Now
            </button>
          )}
        </div>
      </div>

      {/* ── Success / error toast after generate ───────────────────────── */}
      <AnimatePresence>
        {generateMutation.isSuccess && (
          <motion.div
            key="gen-success"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              background: 'rgba(34,197,94,0.1)',
              border: '1px solid rgba(34,197,94,0.3)',
              borderRadius: '10px',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '0.875rem',
              color: 'var(--accent-green, #22c55e)',
            }}
          >
            <CheckCircle2 size={16} />
            {generateMutation.data?.message} (Report ID: {generateMutation.data?.report_id})
          </motion.div>
        )}
        {generateMutation.isError && (
          <motion.div
            key="gen-error"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: '10px',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '0.875rem',
              color: 'var(--accent-red, #ef4444)',
            }}
          >
            <XCircle size={16} />
            Generation failed. Check that you have analyst+ role and the backend is running.
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Stats bar ──────────────────────────────────────────────────── */}
      {hasReports && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
          {[
            { label: 'Total Reports', value: reports!.length, icon: <FileText size={16} /> },
            {
              label: 'Ready',
              value: reports!.filter((r) => r.status === 'success').length,
              icon: <CheckCircle2 size={16} color="var(--accent-green, #22c55e)" />,
            },
            {
              label: 'Pending',
              value: reports!.filter((r) => r.status === 'pending').length,
              icon: <Loader2 size={16} color="var(--accent-yellow, #f59e0b)" />,
            },
            {
              label: 'Failed',
              value: reports!.filter((r) => r.status === 'failed').length,
              icon: <XCircle size={16} color="var(--accent-red, #ef4444)" />,
            },
          ].map((stat) => (
            <div
              key={stat.label}
              id={`stat-${stat.label.toLowerCase().replace(/ /g, '-')}`}
              className="card"
              style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}
            >
              {stat.icon}
              <div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{stat.value}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{stat.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Schedule info card ─────────────────────────────────────────── */}
      <div
        id="schedule-info-card"
        className="card"
        style={{
          padding: '14px 18px',
          display: 'flex',
          alignItems: 'center',
          gap: '14px',
          background: 'linear-gradient(135deg, rgba(59,130,246,0.08) 0%, transparent 60%)',
          border: '1px solid rgba(59,130,246,0.18)',
        }}
      >
        <Calendar size={18} color="var(--accent-blue)" style={{ flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
            Automatic schedule: Every Monday at 09:00 UTC
          </div>
          <div style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Next run: <strong>{nextScheduledRun()}</strong>
          </div>
        </div>
        <Clock size={14} color="var(--text-secondary)" />
      </div>

      {/* ── Reports table ──────────────────────────────────────────────── */}
      <div className="card" style={{ overflow: 'hidden', padding: 0 }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileText size={15} color="var(--accent-blue)" />
          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Generated Reports</span>
        </div>

        {isLoading && (
          <div style={{ padding: '48px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <Loader2 size={24} className="spin" style={{ display: 'block', margin: '0 auto 12px' }} />
            Loading reports…
          </div>
        )}

        {isError && (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--accent-red, #ef4444)' }}>
            Failed to load reports list.
          </div>
        )}

        {!isLoading && !isError && !hasReports && (
          <div style={{
            padding: '56px 24px',
            textAlign: 'center',
            color: 'var(--text-secondary)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}>
            <FileText size={40} style={{ opacity: 0.25 }} />
            <div>
              <p style={{ fontWeight: 600, color: 'var(--text-primary)' }}>No reports yet</p>
              <p style={{ fontSize: '0.875rem' }}>
                {canGenerate
                  ? 'Click "Generate Now" to create the first PDF report.'
                  : 'Reports will appear here once an analyst generates them.'}
              </p>
            </div>
            {canGenerate && (
              <button
                id="empty-state-generate-btn"
                className="btn btn-primary"
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
                style={{ gap: '6px', marginTop: '4px' }}
              >
                <Play size={14} />
                Generate First Report
              </button>
            )}
          </div>
        )}

        {hasReports && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--surface-3, rgba(255,255,255,0.03))', borderBottom: '1px solid var(--border)' }}>
                  {['Week', 'Generated At', 'Status', 'File Size', 'Actions'].map((col) => (
                    <th
                      key={col}
                      style={{
                        padding: '10px 16px',
                        textAlign: 'left',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        color: 'var(--text-secondary)',
                        letterSpacing: '0.05em',
                        textTransform: 'uppercase',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reports!.map((report, i) => (
                  <ReportRow
                    key={report.id}
                    report={report}
                    index={i}
                    onPreview={(id) => setPreviewId(id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── How it works card ──────────────────────────────────────────── */}
      <div className="card" style={{ padding: '18px 20px' }}>
        <h3 style={{ fontWeight: 700, fontSize: '0.875rem', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ChevronRight size={14} color="var(--accent-blue)" />
          How It Works
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          {[
            { step: '01', title: 'Triggered', desc: 'Every Monday at 09:00 UTC or manually for analysts+' },
            { step: '02', title: 'Generated', desc: 'ReportLab builds a 5-page PDF with KPIs, OTIF chart, seller list, and flagged shipments' },
            { step: '03', title: 'Uploaded', desc: 'PDF saved to S3 as reports/weekly_report_YYYY-WW.pdf' },
            { step: '04', title: 'Downloaded', desc: 'Secure presigned URL valid for 15 minutes' },
          ].map(({ step, title, desc }) => (
            <div key={step} style={{ display: 'flex', gap: '12px' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '8px',
                background: 'rgba(59,130,246,0.15)',
                color: 'var(--accent-blue)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.7rem',
                fontWeight: 700,
                flexShrink: 0,
              }}>
                {step}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{title}</div>
                <div style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', marginTop: '2px', lineHeight: 1.4 }}>{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Preview modal ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {previewId !== null && (
          <PreviewModal reportId={previewId} onClose={() => setPreviewId(null)} />
        )}
      </AnimatePresence>
    </motion.div>
  )
}
