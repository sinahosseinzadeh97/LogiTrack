import type { ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { errorMessage } from '@/api/client'
import { EmptyState } from './EmptyState'
import { SkeletonTable } from './SkeletonCard'

interface QueryStateProps {
  isLoading: boolean
  error: unknown
  isEmpty?: boolean
  emptyTitle?: string
  loading?: ReactNode
  children: ReactNode
}

/** Renders the loading, error or empty state of a query, otherwise its children. */
export function QueryState({ isLoading, error, isEmpty, emptyTitle = 'Nothing to show', loading, children }: QueryStateProps) {
  if (isLoading) return <>{loading ?? <SkeletonTable rows={6} />}</>
  if (error) {
    return <EmptyState title="Could not load data" description={errorMessage(error)} icon={<AlertTriangle size={36} />} />
  }
  if (isEmpty) return <EmptyState title={emptyTitle} description="Try a different filter or date range." />
  return <>{children}</>
}
