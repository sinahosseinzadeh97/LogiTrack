import apiClient from './client'

export interface ModelInfo {
  model_version: string
  trained_at: string
  features: string[]
  algorithm: string
  roc_auc: number
}

export interface FeatureImportance {
  feature: string
  importance: number
}

export interface RetrainResponse {
  task_id: string
  message: string
}

export interface RetrainStatus {
  task_id: string
  status: 'pending' | 'running' | 'complete' | 'failed'
  message: string
}

export const mlApi = {
  getModelInfo: () =>
    apiClient.get<ModelInfo>('/api/v1/ml/model-info').then((r) => r.data),

  getFeatureImportance: () =>
    apiClient.get<FeatureImportance[]>('/api/v1/ml/feature-importance').then((r) => r.data),

  triggerRetrain: () =>
    apiClient.post<RetrainResponse>('/api/v1/ml/retrain').then((r) => r.data),

  getRetrainStatus: (taskId: string) =>
    apiClient.get<RetrainStatus>(`/api/v1/ml/retrain-status/${taskId}`).then((r) => r.data),
}
