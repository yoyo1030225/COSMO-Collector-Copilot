<script setup lang="ts">
import type { CollectionSnapshot } from '~/types/objekt'
import { parseCollectionSnapshot } from '~/utils/collection'

const PAGE_SIZE = 60
// 先顯示上次成功結果；服務尚未啟動時，仍可瀏覽原有本機快照。
const { data, status, error } = await useAsyncData<CollectionSnapshot>('collection-view', async () => {
  let snapshot: unknown
  try {
    snapshot = await $fetch('/api/collections/latest', { retry: 0, timeout: 5000 })
  }
  catch {
    snapshot = await $fetch('/data/collection.json', { retry: 0, timeout: 5000 })
  }
  return parseCollectionSnapshot(snapshot)
})
const nickname = ref(data.value?.account.nickname ?? '')
const requestedNickname = ref('')
const { isLoading: lookupPending, progress: lookupProgress, error: lookupError, load: loadCollection } = useCollectionLookup()
watch(nickname, () => { lookupError.value = '' })
const search = ref('')
const member = ref('')
const season = ref('')
const currentPage = ref(1)
const allCards = computed(() => data.value?.objekts ?? [])
const members = computed(() => [...new Set(allCards.value.flatMap(card => card.members))].sort())
const seasons = computed(() => [...new Set(allCards.value.map(card => card.season))].sort())
const filteredCards = computed(() => {
  const query = search.value.trim().toLowerCase()
  return allCards.value.filter(card => (!member.value || card.members.includes(member.value))
    && (!season.value || card.season === season.value)
    && [card.member, ...card.members, card.season, card.collection_code, card.artist, card.external_token_id]
      .join(' ').toLowerCase().includes(query))
})
const pageCount = computed(() => Math.max(1, Math.ceil(filteredCards.value.length / PAGE_SIZE)))
const pageCards = computed(() => filteredCards.value.slice((currentPage.value - 1) * PAGE_SIZE, currentPage.value * PAGE_SIZE))
const rangeStart = computed(() => filteredCards.value.length ? (currentPage.value - 1) * PAGE_SIZE + 1 : 0)
const rangeEnd = computed(() => Math.min(currentPage.value * PAGE_SIZE, filteredCards.value.length))
watch([search, member, season, data], () => { currentPage.value = 1 })

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-TW', { timeZone: 'Asia/Taipei', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

async function changePage(page: number) {
  currentPage.value = Math.max(1, Math.min(pageCount.value, page))
  await nextTick()
  document.getElementById('collection-start')?.scrollIntoView({ block: 'start' })
}

function clearFilters() {
  search.value = ''
  member.value = ''
  season.value = ''
}

async function lookupCollection() {
  const target = nickname.value.trim().replace(/^@/, '')
  if (!target || lookupPending.value) return
  requestedNickname.value = target
  const snapshot = await loadCollection(target)
  if (!snapshot) return
  data.value = snapshot
  error.value = undefined
  nickname.value = snapshot.account.nickname
  clearFilters()
}
</script>

<template>
  <div class="site-shell gallery-shell">
    <a class="skip-link" href="#main">跳至主要內容</a>
    <header class="site-header">
      <a class="brand" href="/" aria-label="COSMO Collector Copilot 首頁">
        <span class="brand-mark" aria-hidden="true" />
        <span>COSMO <span class="brand-detail">Collector Copilot</span></span>
      </a>
      <span class="header-section">個人圖鑑</span>
    </header>

    <main id="main" :aria-busy="status === 'pending'">
      <div class="page-heading gallery-heading">
        <div>
          <p class="eyebrow">YOUR OBJEKT COLLECTION</p>
          <h1>個人 Objekt 圖鑑</h1>
          <p v-if="data" class="page-description">{{ data.account.nickname }} <span class="wallet-short">{{ data.account.address.slice(0, 6) }}…{{ data.account.address.slice(-4) }}</span></p>
          <p v-else class="page-description">每一張收藏，都有屬於自己的位置。</p>
        </div>
        <span v-if="data && !error" class="preview-label">完整持有快照</span>
      </div>

      <form class="nickname-lookup" :aria-busy="lookupPending" @submit.prevent="lookupCollection">
        <label for="cosmo-nickname">COSMO 暱稱</label>
        <div class="nickname-input-row">
          <input id="cosmo-nickname" v-model="nickname" type="text" maxlength="65" autocomplete="off" placeholder="例如 unproKPOPfan225" :disabled="lookupPending" required>
          <button type="submit" class="lookup-button" :disabled="lookupPending || !nickname.trim().replace(/^@/, '')">{{ lookupPending ? '讀取中…' : '讀取收藏' }}</button>
        </div>
        <p class="lookup-hint">輸入 COSMO App 顯示的暱稱，取得目前持有的卡片。</p>
        <div v-if="lookupPending" class="lookup-progress" role="status" aria-live="polite">
          <span class="loading-spinner" aria-hidden="true" />
          <span>正在讀取「{{ requestedNickname }}」：{{ lookupProgress }}</span>
        </div>
        <p v-if="lookupPending && data" class="lookup-preserved">下方仍顯示「{{ data.account.nickname }}」的上次成功快照，完成後更新。</p>
        <p v-if="lookupError" class="lookup-error" role="alert">{{ lookupError }}<span v-if="data"> 下方已保留「{{ data.account.nickname }}」的上次成功收藏。</span></p>
      </form>

      <section v-if="!data && (status === 'pending' || lookupPending)" class="message-panel" aria-live="polite">
        <span class="loading-spinner" aria-hidden="true" /><h2>正在載入收藏</h2><p>為你整理每一張 Objekt。</p>
      </section>
      <section v-else-if="!data" class="message-panel">
        <p class="eyebrow">從你的收藏開始</p><h2>輸入暱稱，開啟個人圖鑑</h2>
        <p>完成讀取後，卡片與完整持有張數會顯示在這裡。</p>
      </section>

      <template v-else>
        <section class="collection-summary" aria-label="完整收藏統計">
          <div class="summary-stat"><span>持有張數</span><strong>{{ data.total.toLocaleString() }}<small>張</small></strong></div>
          <div class="summary-stat"><span>不同卡款</span><strong>{{ data.unique_collections.toLocaleString() }}<small>款</small></strong></div>
          <div class="summary-sync"><span>最後成功同步</span><strong>{{ formatTime(data.fetched_at) }}</strong><span>台北時間 · Abstract</span></div>
        </section>

        <section class="collection-filters" aria-label="篩選收藏">
          <label class="search-field"><span>搜尋收藏</span><input v-model="search" type="search" placeholder="成員、季節、卡款代碼或 Token ID"></label>
          <label><span>成員</span><select v-model="member" aria-label="成員"><option value="">全部成員</option><option v-for="name in members" :key="name" :value="name">{{ name }}</option></select></label>
          <label><span>季節</span><select v-model="season" aria-label="季節"><option value="">全部季節</option><option v-for="name in seasons" :key="name" :value="name">{{ name }}</option></select></label>
        </section>

        <div id="collection-start" class="results-row" aria-live="polite">
          <p>顯示 {{ rangeStart }}–{{ rangeEnd }}／{{ filteredCards.length }} 張</p>
          <span>共 {{ data.total }} 張已載入 · Token ID 由大到小</span>
        </div>
        <div v-if="pageCards.length" class="collection-grid">
          <OwnedObjektCard v-for="card in pageCards" :key="card.external_token_id" :objekt="card" />
        </div>
        <section v-else class="empty-collection" aria-live="polite">
          <h2>{{ data.total === 0 ? '目前沒有持有的 Objekt' : '找不到符合條件的卡片' }}</h2>
          <button v-if="data.total" class="button" @click="clearFilters">清除篩選</button>
        </section>

        <nav class="collection-pagination" aria-label="收藏分頁">
          <button class="pagination-button" :disabled="currentPage === 1" @click="changePage(currentPage - 1)">上一頁</button>
          <label>第 <select v-model.number="currentPage" aria-label="頁碼" @change="changePage(currentPage)"><option v-for="number in pageCount" :key="number" :value="number">{{ number }}</option></select>／{{ pageCount }} 頁</label>
          <button class="pagination-button" :disabled="currentPage === pageCount" @click="changePage(currentPage + 1)">下一頁</button>
        </nav>

        <div class="source-panel collection-source">
          <div><p class="source-title">持有紀錄 · Abstract 區塊 {{ data.block_number.toLocaleString() }}</p><p class="source-time">持有時點：{{ formatTime(data.ownership_at) }} · 卡片資料：COSMO 官方</p></div>
          <a class="source-link" :href="`https://abscan.org/address/${data.account.address}`" target="_blank" rel="noopener noreferrer">查看錢包</a>
        </div>
        <p class="collection-note">完整載入 {{ data.total }} 張，每頁顯示 {{ PAGE_SIZE }} 張。同款不同張以各自的 Token ID 保留。</p>
      </template>
    </main>
    <footer class="site-footer"><span>COSMO Collector Copilot</span><span>一張一張，建立你的收藏視角。</span></footer>
  </div>
</template>
