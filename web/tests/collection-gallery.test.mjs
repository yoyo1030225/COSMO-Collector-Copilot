import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'
import { compileScript, parse } from 'vue/compiler-sfc'
import ts from 'typescript'
import { computed, effectScope, nextTick, onScopeDispose, ref, shallowRef, watch } from 'vue'

const require = createRequire(import.meta.url)

function loadTypeScript(source, globals = {}) {
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  })
  const context = { exports: {}, require, ...globals }
  vm.runInNewContext(outputText, context)
  return context.exports
}

const { descriptor } = parse(readFileSync(new URL('../app/components/CollectionGallery.vue', import.meta.url), 'utf8'))
const galleryScript = compileScript(descriptor, { id: 'collection-gallery-test' }).content
const collectionUtils = loadTypeScript(readFileSync(new URL('../app/utils/collection.ts', import.meta.url), 'utf8'))
const { parseCollectionSnapshot } = collectionUtils
const lookupScript = readFileSync(new URL('../app/composables/useCollectionLookup.ts', import.meta.url), 'utf8')

function createGallery(t, load, { preview = shallowRef(null), isLoading = ref(false), prioritize = () => {} } = {}) {
  const component = loadTypeScript(galleryScript, {
    computed, nextTick, ref, shallowRef, watch,
    useCollectionLookup: () => ({ isLoading, progress: ref(''), error: ref(''), preview, load, prioritize }),
  }).default
  const scope = effectScope()
  t.after(() => scope.stop())
  return scope.run(() => component.setup({}, { expose() {} }))
}

function createLookup(t, fetch) {
  const { useCollectionLookup } = loadTypeScript(lookupScript, {
    ref, shallowRef, onScopeDispose, AbortSignal, AbortController,
    setTimeout: callback => queueMicrotask(callback),
    $fetch: fetch, require: path => path === '~/utils/collection' ? collectionUtils : require(path),
  })
  const scope = effectScope()
  t.after(() => scope.stop())
  return scope.run(useCollectionLookup)
}

function snapshot(total) {
  return parseCollectionSnapshot({
    account: { nickname: 'example', address: '0x' + '1'.repeat(40) },
    complete: true, total, unique_collections: 1,
    objekts: Array.from({ length: total }, (_, index) => ({
      external_token_id: String(total - index), name: 'Sample Objekt', artist: 'Example',
      member: 'Member', members: ['Member'], season: 'Season01', collection_code: '101Z',
      class_name: 'First', image_url: 'https://example.invalid/card.webp',
    })),
    chain_id: 2741, chain_name: 'Abstract', contract_address: '0x99bb83ae9bb0c0a6be865cacf67760947f91cb70',
    block_number: 100, block_hash: '0x' + '2'.repeat(64),
    ownership_at: '2000-01-01T00:00:00Z', fetched_at: '2000-01-01T00:00:00Z',
    ownership_source: 'https://api.mainnet.abs.xyz', metadata_source: 'https://api.cosmo.fans',
  })
}

test('opens with an empty nickname and collection without a saved-data fetch', (t) => {
  // 不提供 useAsyncData 或 $fetch；若開頁又開始自動載入，這裡會失敗。
  const state = createGallery(t, () => { throw new Error('Lookup must wait for user input') })
  assert.equal(state.nickname.value, '')
  assert.equal(state.data.value, null)
  assert.equal(state.pageCards.value.length, 0)
})

test('displays all 10001 records across pages and reaches the final card', async (t) => {
  const data = snapshot(10001)
  const state = createGallery(t, async (nickname) => {
    assert.equal(nickname, 'example')
    return data
  })
  state.nickname.value = ' @example '
  await state.lookupCollection()
  assert.equal(state.data.value.total, 10001)
  assert.equal(state.pageCount.value, 167)
  assert.equal(state.pageCards.value.length, 60)
  assert.equal(state.pageCards.value[0].external_token_id, '10001')
  state.currentPage.value = 167
  assert.equal(state.rangeStart.value, 9961)
  assert.equal(state.rangeEnd.value, 10001)
  assert.equal(state.pageCards.value.length, 41)
  assert.equal(state.pageCards.value.at(-1).external_token_id, '1')
})

test('prioritizes the visible page when moving to the end of a large collection', async (t) => {
  const data = snapshot(10001)
  const preview = shallowRef(null)
  const priorities = []
  const state = createGallery(t, async () => null, {
    preview, isLoading: ref(true), prioritize: tokens => priorities.push([...tokens]),
  })
  const tokenIds = data.objekts.map(card => card.external_token_id)
  preview.value = { account: data.account, tokenIds, cards: new Map() }
  await nextTick()
  assert.deepEqual(priorities, [tokenIds.slice(0, 60)])
  state.currentPage.value = 167
  await nextTick()
  assert.deepEqual(priorities, [tokenIds.slice(0, 60), tokenIds.slice(9960)])

  const ready = data.objekts[9960]
  preview.value = { ...preview.value, cards: new Map([[ready.external_token_id, ready]]) }
  await nextTick()
  assert.equal('member' in state.pageCards.value[0], true)
  assert.equal(priorities.length, 2)
})

test('keeps the last success when a later lookup fails', async (t) => {
  const data = snapshot(2)
  const state = createGallery(t, async nickname => nickname === 'example' ? data : null)
  state.nickname.value = 'example'
  await state.lookupCollection()
  state.nickname.value = 'missing'
  await state.lookupCollection()
  assert.equal(state.data.value, data)
})

test('shows every verified holding even if some card details are unavailable', async (t) => {
  const previous = snapshot(2)
  const lookupPreview = shallowRef(null)
  const state = createGallery(t, async nickname => {
    if (nickname === 'example') return previous
    lookupPreview.value = {
      account: { nickname, address: '0x' + '2'.repeat(40) },
      tokenIds: ['5', '4', '3'],
      cards: new Map([['4', { ...previous.objekts[0], external_token_id: '4' }]]),
    }
    return null
  }, { preview: lookupPreview })
  state.nickname.value = 'example'
  await state.lookupCollection()
  state.nickname.value = 'other-example'
  await state.lookupCollection()
  assert.equal(state.data.value, previous)
  assert.equal(state.account.value.nickname, 'other-example')
  assert.equal(state.total.value, 3)
  assert.equal(state.pageCards.value[0].external_token_id, '5')
  assert.equal('member' in state.pageCards.value[0], false)
  assert.equal('member' in state.pageCards.value[1], true)
})

test('polling restores the verified token order across multiple responses', async (t) => {
  const data = snapshot(2)
  const { objekts, ...result } = data
  const initial = { job_id: 'a'.repeat(32), nickname: 'example', status: 'queued', progress: '準備中' }
  const update = {
    ...initial, account: data.account, total: null, token_ids: null, cards: [],
    next_cursor: 0, has_more: false, result: null,
  }
  const responses = [
    initial,
    { ...update, status: 'running' },
    { ...update, status: 'running', total: 2, token_ids: ['2', '1'], cards: [objekts[1]], next_cursor: 1, has_more: true },
    { ...update, status: 'succeeded', total: 2, cards: [objekts[0]], next_cursor: 2, result },
  ]
  const cursors = []
  const lookup = createLookup(t, async (_url, options) => {
    if (options.query) cursors.push([options.query.cursor, options.query.include_tokens])
    if (responses.length === 2) {
      assert.equal(lookup.preview.value.account.nickname, 'example')
      assert.equal(lookup.preview.value.tokenIds, null)
    }
    return responses.shift()
  })
  const finished = await lookup.load('example')
  assert.ok(finished, lookup.error.value)
  assert.deepEqual(cursors, [[0, true], [0, true], [1, false]])
  assert.equal(finished.objekts.map(card => card.external_token_id).join(','), '2,1')
})

test('sends only the latest page when the user changes pages during a priority request', async (t) => {
  const data = snapshot(3)
  const { objekts, ...result } = data
  const tokenIds = objekts.map(card => card.external_token_id)
  const initial = { job_id: 'a'.repeat(32), nickname: 'example', status: 'queued', progress: '準備中' }
  const running = {
    ...initial, status: 'running', account: data.account, total: 3, token_ids: tokenIds, cards: [],
    next_cursor: 0, has_more: false, result: null,
  }
  const { promise: polling, resolve: ready } = Promise.withResolvers()
  const { promise: finalPoll, resolve: finish } = Promise.withResolvers()
  const { promise: firstRequest, resolve: releaseFirst } = Promise.withResolvers()
  const { promise: lastRequest, resolve: sentLast } = Promise.withResolvers()
  const priorities = []
  let firstPoll = true
  const lookup = createLookup(t, async (url, options) => {
    if (url.endsWith('/prioritize')) {
      priorities.push([...options.body.token_ids])
      if (priorities.length === 1) return firstRequest
      sentLast()
      return
    }
    if (url.endsWith('/sync')) return initial
    if (firstPoll) {
      firstPoll = false
      return running
    }
    ready()
    return finalPoll
  })
  const loading = lookup.load('example')
  await polling
  lookup.prioritize(['3'])
  lookup.prioritize(['2'])
  lookup.prioritize(['1'])
  assert.deepEqual(priorities, [['3']])
  releaseFirst()
  await lastRequest
  assert.deepEqual(priorities, [['3'], ['1']])
  finish({ ...running, status: 'succeeded', token_ids: null, cards: objekts, next_cursor: 3, result })
  assert.equal((await loading)?.total, 3)
})
