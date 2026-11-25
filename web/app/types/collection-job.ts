export interface CollectionJob {
  job_id: string
  nickname: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  progress: string
  error?: string | null
  snapshot?: unknown
}
import type { CollectionAccount, Objekt } from '~/types/objekt'


export interface CollectionJobUpdate extends CollectionJob {
  account: CollectionAccount | null
  total: number | null
  token_ids: string[] | null
  cards: Objekt[]
  next_cursor: number
  has_more: boolean
  result: unknown
}

export interface CollectionPreview {
  account: CollectionAccount
  tokenIds: string[] | null
  cards: ReadonlyMap<string, Objekt>
}
