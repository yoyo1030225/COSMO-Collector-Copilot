import type { CollectionAccount, CollectionSnapshot, Objekt } from '~/types/objekt'

export function isCollectionAccount(value: unknown): value is CollectionAccount {
  if (!value || typeof value !== 'object') return false
  const account = value as Partial<CollectionAccount>
  return typeof account.nickname === 'string' && !!account.nickname.trim()
    && typeof account.address === 'string' && /^0x[0-9a-fA-F]{40}$/.test(account.address)
}

export function isObjekt(value: unknown): value is Objekt {
  if (!value || typeof value !== 'object') return false
  const card = value as Partial<Objekt>
  const fields = ['external_token_id', 'name', 'artist', 'member', 'season', 'collection_code', 'class_name', 'image_url'] as const
  return fields.every(key => typeof card[key] === 'string' && card[key].trim().length > 0)
    && Array.isArray(card.members) && card.members.length > 0
    && card.members.every(member => typeof member === 'string' && member.trim().length > 0)
    && /^[0-9]+$/.test(card.external_token_id!)
    && card.image_url!.startsWith('https://')
}

export function parseCollectionSnapshot(value: unknown): CollectionSnapshot {
  if (!value || typeof value !== 'object') throw new Error('收藏資料不是有效的 JSON 物件。')
  const snapshot = value as Partial<CollectionSnapshot>
  if (
    snapshot.complete !== true
    || !isCollectionAccount(snapshot.account)
    || !Array.isArray(snapshot.objekts)
    || !snapshot.objekts.every(isObjekt)
    || !Number.isSafeInteger(snapshot.total)
    || snapshot.total !== snapshot.objekts.length
    || new Set(snapshot.objekts.map(card => card.external_token_id)).size !== snapshot.total
    || snapshot.chain_id !== 2741
    || snapshot.chain_name !== 'Abstract'
    || snapshot.contract_address !== '0x99bb83ae9bb0c0a6be865cacf67760947f91cb70'
    || !Number.isSafeInteger(snapshot.block_number)
    || typeof snapshot.block_hash !== 'string'
    || !/^0x[0-9a-fA-F]{64}$/.test(snapshot.block_hash)
    || typeof snapshot.ownership_at !== 'string'
    || !Number.isFinite(Date.parse(snapshot.ownership_at))
    || typeof snapshot.fetched_at !== 'string'
    || !Number.isFinite(Date.parse(snapshot.fetched_at))
    || snapshot.ownership_source !== 'https://api.mainnet.abs.xyz'
    || snapshot.metadata_source !== 'https://api.cosmo.fans'
  ) throw new Error('收藏快照不完整，或持有張數、Token ID 與來源資訊不符。')

  const definitions = new Set(snapshot.objekts.map(card => JSON.stringify([
    card.artist, card.season, card.member, card.collection_code,
  ])))
  if (snapshot.unique_collections !== definitions.size) throw new Error('卡款統計與收藏資料不符。')
  return snapshot as CollectionSnapshot
}
