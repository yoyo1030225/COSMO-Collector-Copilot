import type { CollectionJob, CollectionJobUpdate, CollectionPreview } from '~/types/collection-job'
import type { CollectionSnapshot, Objekt } from '~/types/objekt'
import { isCollectionAccount, isObjekt, parseCollectionSnapshot } from '~/utils/collection'

const POLL_DELAY = 1000
const REQUEST_TIMEOUT = 10000

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

function parseUpdate(job: CollectionJob, cursor: number): CollectionJobUpdate {
  const update = job as Partial<CollectionJobUpdate>
  if ((update.account !== null && !isCollectionAccount(update.account))
    || (update.total !== null && (typeof update.total !== 'number' || !Number.isSafeInteger(update.total) || update.total < 0))
    || !Array.isArray(update.cards) || !update.cards.every(isObjekt)
    || update.next_cursor !== cursor + update.cards.length
    || typeof update.has_more !== 'boolean' || (update.has_more && !update.cards.length)) {
    throw new Error('收藏服務回傳的更新格式不正確。')
  }
  if (update.token_ids !== null && (!Array.isArray(update.token_ids)
    || update.token_ids.length !== update.total || new Set(update.token_ids).size !== update.total
    || update.token_ids.some(token => typeof token !== 'string' || !/^[0-9]+$/.test(token)))) {
    throw new Error('持有清單的張數或 Token ID 不符。')
  }
  return update as CollectionJobUpdate
}

function requestSignal(signal: AbortSignal) {
  return AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT)])
}

function checkNickname(actual: string, requested: string) {
  if (actual.toLowerCase() !== requested.toLowerCase()) {
    throw new Error('回應帳號與輸入的暱稱不一致。')
  }
}

export function useCollectionLookup() {
  const isLoading = ref(false)
  const progress = ref('')
  const error = ref('')
  const preview = shallowRef<CollectionPreview | null>(null)
  let disposed = false
  let controller: AbortController | undefined
  let sendPriority: ((tokenIds: string[]) => Promise<void>) | undefined
  onScopeDispose(() => { disposed = true; controller?.abort() })

  function prioritize(tokenIds: string[]) {
    void sendPriority?.(tokenIds)
  }

  async function load(nickname: string): Promise<CollectionSnapshot | null> {
    if (isLoading.value) return null
    error.value = ''
    preview.value = null
    isLoading.value = true
    progress.value = '正在建立收藏查詢…'
    controller = new AbortController()
    const signal = controller.signal
    let tokenIds: string[] | null = null
    let ownedTokens = new Set<string>()
    const cards = new Map<string, Objekt>()
    let cursor = 0
    try {
      const initial = parseJob(await $fetch('/api/collections/sync', {
        method: 'POST', body: { nickname }, retry: 0, signal: requestSignal(signal),
      }))
      const jobUrl = `/api/collections/jobs/${initial.job_id}`
      let pendingPriority: string[] | null = null
      let sendingPriority = false
      let lastPriorityKey = ''
      sendPriority = async (tokenIds) => {
        const key = tokenIds.join(',')
        if (key === lastPriorityKey) return
        lastPriorityKey = key
        pendingPriority = tokenIds
        if (sendingPriority) return
        sendingPriority = true
        try {
          // 快速連續翻頁時，等目前請求送完，只補送最後選擇的頁面。
          while (pendingPriority !== null && !signal.aborted) {
            const pageTokens = pendingPriority
            pendingPriority = null
            try {
              await $fetch(`${jobUrl}/prioritize`, {
                method: 'POST', body: { token_ids: pageTokens }, retry: 0, signal: requestSignal(signal),
              })
            }
            catch {
              // 提示送不出去時，背景仍會依序補齊整份收藏。
            }
          }
        }
        finally {
          sendingPriority = false
        }
      }
      progress.value = initial.progress
      let delay = 0
      while (!disposed) {
        if (delay) await new Promise(resolve => setTimeout(resolve, delay))
        if (disposed) return null
        const job = parseJob(await $fetch(jobUrl, {
          query: { cursor, include_tokens: tokenIds === null },
          retry: 2, retryDelay: 750, signal: requestSignal(signal),
        }))
        if (disposed) return null
        progress.value = job.progress

        // 核對後的 Token ID 順序固定。卡片資料可按完成順序抵達。
        if ('next_cursor' in job) {
          const update = parseUpdate(job, cursor)
          if (update.account) checkNickname(update.account.nickname, nickname)
          if (update.token_ids !== null) {
            tokenIds = update.token_ids
            ownedTokens = new Set(tokenIds)
          }
          if (update.total === null && tokenIds !== null) {
            tokenIds = null  // 區塊重驗失敗，撤回暫時顯示的持有清單。
            ownedTokens.clear()
            cards.clear()
          }
          for (const card of update.cards) {
            if (!ownedTokens.has(card.external_token_id) || cards.has(card.external_token_id)) {
              throw new Error('卡片資料與持有清單不符。')
            }
            cards.set(card.external_token_id, card)
          }
          cursor = update.next_cursor
          if (update.account && (preview.value?.account.address !== update.account.address
            || preview.value?.tokenIds !== tokenIds || update.cards.length)) {
            preview.value = { account: update.account, tokenIds, cards }
          }
          if (update.has_more) {
            delay = 0
            continue
          }
          if (update.status === 'succeeded') {
            const snapshot = parseCollectionSnapshot({
              ...(update.result as object),
              objekts: tokenIds?.map(token => cards.get(token)),
            })
            checkNickname(snapshot.account.nickname, nickname)
            return snapshot
          }
        }
        else if (job.status === 'succeeded') {
          // 尚未重啟的舊版 API 仍以整份快照回應。
          const snapshot = parseCollectionSnapshot(job.snapshot)
          checkNickname(snapshot.account.nickname, nickname)
          return snapshot
        }

        if (job.status === 'failed') throw new Error(job.error || '收藏讀取失敗，請稍後重試。')
        delay = POLL_DELAY
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
      sendPriority = undefined
      controller.abort()
      isLoading.value = false
    }
    return null
  }

  return { isLoading, progress, error, preview, load, prioritize }
}
