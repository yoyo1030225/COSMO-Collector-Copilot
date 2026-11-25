<script setup lang="ts">
import type { CollectionSnapshot, Objekt } from '~/types/objekt'

const PAGE_SIZE = 60
// 開頁從空白開始。data 只保存完整快照，進行中的查詢另外顯示。
const data = shallowRef<CollectionSnapshot | null>(null)
const nickname = ref('')
const requestedNickname = ref('')
const {
  isLoading: lookupPending, progress: lookupProgress, error: lookupError,
  preview: lookupPreview, load: loadCollection, prioritize,
} = useCollectionLookup()
watch(nickname, () => { lookupError.value = '' })
const search = ref('')
const member = ref('')
const season = ref('')
const currentPage = ref(1)
const preview = computed(() => {
  const current = lookupPreview.value
  if (lookupPending.value || !data.value || current?.tokenIds != null) return current
  return null
})
const snapshot = computed(() => preview.value ? null : data.value)
const account = computed(() => preview.value?.account ?? snapshot.value?.account)
const total = computed(() => preview.value ? preview.value.tokenIds?.length : snapshot.value?.total)

const allCards = computed<(Objekt | Pick<Objekt, 'external_token_id'>)[]>(() => {
  const current = preview.value
  if (!current) return snapshot.value?.objekts ?? []
  return current.tokenIds?.map(token => current.cards.get(token) ?? { external_token_id: token }) ?? []
})
const knownCards = computed(() => preview.value ? Array.from(preview.value.cards.values()) : snapshot.value?.objekts ?? [])
const members = computed(() => [...new Set(knownCards.value.flatMap(card => card.members))].sort())
const seasons = computed(() => [...new Set(knownCards.value.map(card => card.season))].sort())
const filteredCards = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query && !member.value && !season.value) return allCards.value
  return allCards.value.filter((card) => {
    if (!('member' in card)) return !member.value && !season.value && card.external_token_id.includes(query)
    return (!member.value || card.members.includes(member.value)) && (!season.value || card.season === season.value)
      && [card.member, ...card.members, card.season, card.collection_code, card.artist, card.external_token_id]
        .join(' ').toLowerCase().includes(query)
  })
})
const pageCount = computed(() => Math.max(1, Math.ceil(filteredCards.value.length / PAGE_SIZE)))
const pageCards = computed(() => filteredCards.value.slice((currentPage.value - 1) * PAGE_SIZE, currentPage.value * PAGE_SIZE))
const rangeStart = computed(() => filteredCards.value.length ? (currentPage.value - 1) * PAGE_SIZE + 1 : 0)
const rangeEnd = computed(() => Math.min(currentPage.value * PAGE_SIZE, filteredCards.value.length))
watch([search, member, season], () => { currentPage.value = 1 })
watch(() => account.value?.address, () => {
  currentPage.value = 1
  clearFilters()
})
watch(pageCount, count => { currentPage.value = Math.min(currentPage.value, count) })
watch(() => lookupPending.value && preview.value?.tokenIds != null
  ? pageCards.value.map(card => card.external_token_id).join(',')
  : null, (pageKey) => {
  if (pageKey === null) return
  prioritize(pageCards.value.filter(card => !('member' in card)).map(card => card.external_token_id))
})

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
  const result = await loadCollection(target)
  if (!result) return
  data.value = result
  lookupPreview.value = null
  nickname.value = result.account.nickname
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

    <main id="main" :class="{ 'collection-entry': !account }">
      <div class="page-heading gallery-heading">
        <div>
          <p class="eyebrow">YOUR OBJEKT COLLECTION</p>
          <h1>{{ account ? '個人 Objekt 圖鑑' : '開啟你的 Objekt 圖鑑' }}</h1>
          <p v-if="account" class="page-description">{{ account.nickname }} <span class="wallet-short">{{ account.address.slice(0, 6) }}…{{ account.address.slice(-4) }}</span></p>
          <p v-else class="page-description">輸入 COSMO 暱稱，查看目前持有的每一張卡片。</p>
        </div>
        <span v-if="snapshot" class="preview-label">完整持有快照</span>
      </div>

      <form class="nickname-lookup" :aria-busy="lookupPending" @submit.prevent="lookupCollection">
        <label for="cosmo-nickname">COSMO 暱稱</label>
        <div class="nickname-input-row">
          <input id="cosmo-nickname" v-model="nickname" type="text" maxlength="65" autocomplete="off" placeholder="輸入你的 COSMO 暱稱" :disabled="lookupPending" required>
          <button type="submit" class="lookup-button" :disabled="lookupPending || !nickname.trim().replace(/^@/, '')">{{ lookupPending ? '讀取中…' : '讀取收藏' }}</button>
        </div>
        <p class="lookup-hint">使用 COSMO App 顯示的暱稱。持有清單核對後，會優先讀取你正在看的那一頁。</p>
        <div v-if="lookupPending" class="lookup-progress" role="status" aria-live="polite">
          <span class="loading-spinner" aria-hidden="true" />
          <span>正在讀取「{{ requestedNickname }}」：{{ lookupProgress }}</span>
        </div>
        <p v-if="lookupPending && snapshot" class="lookup-preserved">下方目前顯示「{{ snapshot.account.nickname }}」的上次成功快照。</p>
        <p v-if="lookupError" class="lookup-error" role="alert">{{ lookupError }}<span v-if="snapshot"> 下方已保留「{{ snapshot.account.nickname }}」的上次成功收藏。</span></p>
      </form>

      <p v-if="!account && !lookupPending && !lookupError" class="entry-note">每次開啟都從這裡開始，查詢後才顯示該帳號的收藏。</p>

      <template v-if="total !== undefined">
        <section class="collection-summary" aria-label="收藏統計">
          <div class="summary-stat"><span>持有張數</span><strong>{{ total.toLocaleString() }}<small>張</small></strong></div>
          <template v-if="snapshot">
            <div class="summary-stat"><span>不同卡款</span><strong>{{ snapshot.unique_collections.toLocaleString() }}<small>款</small></strong></div>
            <div class="summary-sync"><span>最後成功同步</span><strong>{{ formatTime(snapshot.fetched_at) }}</strong><span>台北時間 · Abstract</span></div>
          </template>
          <template v-else-if="preview">
            <div class="summary-stat"><span>已讀取卡片資料</span><strong>{{ preview.cards.size.toLocaleString() }}<small>張</small></strong></div>
            <div class="summary-sync"><span>持有來源</span><strong>Abstract</strong><span>鏈上持有清單已核對</span></div>
          </template>
        </section>

        <p v-if="preview && preview.cards.size < total" class="filter-note">成員與季節篩選會隨卡片資料更新。Token ID 可直接搜尋。</p>
        <section class="collection-filters" aria-label="篩選收藏">
          <label class="search-field"><span>搜尋收藏</span><input v-model="search" type="search" placeholder="成員、季節、卡款代碼或 Token ID"></label>
          <label><span>成員</span><select v-model="member" aria-label="成員"><option value="">全部成員</option><option v-for="name in members" :key="name" :value="name">{{ name }}</option></select></label>
          <label><span>季節</span><select v-model="season" aria-label="季節"><option value="">全部季節</option><option v-for="name in seasons" :key="name" :value="name">{{ name }}</option></select></label>
        </section>

        <div id="collection-start" class="results-row" aria-live="polite">
          <p>顯示 {{ rangeStart.toLocaleString() }}–{{ rangeEnd.toLocaleString() }}／{{ filteredCards.length.toLocaleString() }} 張</p>
          <span>持有共 {{ total.toLocaleString() }} 張 · Token ID 由大到小</span>
        </div>
        <div v-if="pageCards.length" class="collection-grid">
          <template v-for="card in pageCards" :key="card.external_token_id">
            <OwnedObjektCard v-if="'member' in card" :objekt="card" />
            <article v-else class="collection-tile" :aria-label="`Token ID ${card.external_token_id}`">
              <div class="tile-image-frame">
                <span class="tile-image-error">{{ lookupPending ? '等待卡片資料' : '卡片資料暫時無法取得' }}</span>
              </div>
              <div class="tile-information"><p class="tile-token">Token ID <span>{{ card.external_token_id }}</span></p></div>
            </article>
          </template>
        </div>
        <section v-else class="empty-collection" aria-live="polite">
          <h2>{{ total === 0 ? '目前沒有持有的 Objekt' : '目前找不到符合條件的卡片' }}</h2>
          <button v-if="total" class="button" @click="clearFilters">清除篩選</button>
        </section>

        <nav class="collection-pagination" aria-label="收藏分頁">
          <button class="pagination-button" :disabled="currentPage === 1" @click="changePage(currentPage - 1)">上一頁</button>
          <label>第 <select v-model.number="currentPage" aria-label="頁碼" @change="changePage(currentPage)"><option v-for="number in pageCount" :key="number" :value="number">{{ number }}</option></select>／{{ pageCount }} 頁</label>
          <button class="pagination-button" :disabled="currentPage === pageCount" @click="changePage(currentPage + 1)">下一頁</button>
        </nav>

        <div v-if="snapshot" class="source-panel collection-source">
          <div><p class="source-title">持有紀錄 · Abstract 區塊 {{ snapshot.block_number.toLocaleString() }}</p><p class="source-time">持有時點：{{ formatTime(snapshot.ownership_at) }} · 卡片資料：COSMO 官方</p></div>
          <a class="source-link" :href="`https://abscan.org/address/${snapshot.account.address}`" target="_blank" rel="noopener noreferrer">查看錢包</a>
        </div>
        <p class="collection-note">每頁顯示 {{ PAGE_SIZE }} 張。同款不同張以各自的 Token ID 保留。</p>
      </template>
    </main>
    <footer class="site-footer"><span>COSMO Collector Copilot</span><span>一張一張，建立你的收藏視角。</span></footer>
  </div>
</template>
