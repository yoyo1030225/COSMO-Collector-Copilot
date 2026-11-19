import type { CollectionJob } from '~/types/collection-job'
import type { CollectionSnapshot } from '~/types/objekt'
import { parseCollectionSnapshot } from '~/utils/collection'

function parseJob(value: unknown): CollectionJob {
  if (!value || typeof value !== 'object') throw new Error('收藏服務沒有回傳有效的查詢資料。')
  const job = value as Partial<CollectionJob>
  if (typeof job.job_id !== 'string' || !/^[a-f0-9]{32}$/.test(job.job_id)
    || typeof job.nickname !== 'string' || typeof job.progress !== 'string'
    || !['queued', 'running', 'succeeded', 'failed'].includes(job.status ?? '')) {
    throw new Error('收藏服務回傳的查詢格式不正確。')
  }
  return job as CollectionJob
}

export function useCollectionLookup() {
  const isLoading = ref(false)
  const progress = ref('')
  const error = ref('')
  let disposed = false
  let controller: AbortController | undefined
  onScopeDispose(() => { disposed = true; controller?.abort() })

  async function load(nickname: string): Promise<CollectionSnapshot | null> {
    if (isLoading.value) return null
    error.value = ''
    isLoading.value = true
    progress.value = '正在建立收藏查詢…'
    controller = new AbortController()
    try {
      let job = parseJob(await $fetch('/api/collections/sync', {
        method: 'POST', body: { nickname }, retry: 0, timeout: 10000, signal: controller.signal,
      }))
      const deadline = Date.now() + 15 * 60 * 1000
      while (!disposed) {
        progress.value = job.progress
        if (job.status === 'failed') throw new Error(job.error || '收藏讀取失敗，請稍後重試。')
        if (job.status === 'succeeded') {
          const snapshot = parseCollectionSnapshot(job.snapshot)
          if (snapshot.account.nickname.toLowerCase() !== nickname.toLowerCase()) {
            throw new Error('回應帳號與輸入的暱稱不一致，已保留原收藏。')
          }
          return snapshot
        }
        if (Date.now() > deadline) throw new Error('查詢時間較長，請稍後再次讀取收藏。')
        await new Promise(resolve => setTimeout(resolve, 1000))
        if (disposed) return null
        job = parseJob(await $fetch(`/api/collections/jobs/${job.job_id}`, {
          retry: 0, timeout: 10000, signal: controller.signal,
        }))
      }
    }
    catch (cause) {
      if (disposed) return null
      const failure = cause as { statusCode?: number; response?: { status?: number }; data?: { detail?: unknown } }
      const status = failure.statusCode ?? failure.response?.status
      if (typeof failure.data?.detail === 'string') error.value = failure.data.detail
      else if (status === 422) error.value = '請輸入有效的 COSMO 暱稱（最多 64 個字元）。'
      else if (status && status >= 500) error.value = '目前無法連線收藏服務，請稍後重試。'
      else error.value = cause instanceof Error ? cause.message : '收藏讀取失敗，請稍後重試。'
    }
    finally {
      isLoading.value = false
    }
    return null
  }

  return { isLoading, progress, error, load }
}
