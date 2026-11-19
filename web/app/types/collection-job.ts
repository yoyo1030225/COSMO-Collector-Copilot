export interface CollectionJob {
  job_id: string
  nickname: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  progress: string
  error?: string | null
  snapshot?: unknown
}
