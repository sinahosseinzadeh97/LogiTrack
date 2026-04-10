import apiClient from './client'

// ── Types ────────────────────────────────────────────────────────────────────

export interface Report {
  id: number
  week: string
  generated_at: string
  s3_path: string | null
  status: 'pending' | 'success' | 'failed'
  file_size_bytes: number | null
}

export interface GenerateResponse {
  message: string
  report_id: number
}

export interface PreviewResponse {
  report_id: number
  pages: string[] // base64-encoded PNG thumbnails
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const reportsApi = {
  /** Return all generated reports, newest first. */
  list: () =>
    apiClient.get<Report[]>('/api/v1/reports').then((r) => r.data),

  /** Trigger a new PDF generation for the current ISO week. */
  generate: () =>
    apiClient
      .post<GenerateResponse>('/api/v1/reports/generate')
      .then((r) => r.data),

  /**
   * Returns the presigned S3 download URL for a report.
   * The backend sends a 307 redirect; we intercept the `Location` header
   * from a HEAD-style call by asking axios NOT to follow redirects and
   * extracting the URL from the response config.
   *
   * In practice, the simplest approach is to open the redirect URL
   * directly in a new tab.  We build the API URL and `window.open` it so
   * the browser follows the redirect natively.
   */
  getDownloadUrl: (id: number): string =>
    `${apiClient.defaults.baseURL ?? ''}/api/v1/reports/${id}/download`,

  /** Return first 3 pages as base64 PNG thumbnails. */
  preview: (id: number) =>
    apiClient
      .get<PreviewResponse>(`/api/v1/reports/${id}/preview`)
      .then((r) => r.data),
}
