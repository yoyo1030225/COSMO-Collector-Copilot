export interface Objekt {
  external_token_id: string
  name: string
  artist: string
  member: string
  members: string[]
  season: string
  collection_code: string
  class_name: string
  image_url: string
}

export interface CollectionSnapshot {
  account: { nickname: string; address: string }
  complete: true
  total: number
  unique_collections: number
  objekts: Objekt[]
  chain_id: number
  chain_name: string
  contract_address: string
  block_number: number
  block_hash: string
  ownership_at: string
  fetched_at: string
  ownership_source: string
  metadata_source: string
}
