<script setup lang="ts">
import type { Objekt } from '~/types/objekt'

defineProps<{ objekt: Objekt }>()
const imageFailed = ref(false)
</script>

<template>
  <article class="collection-tile" :aria-label="`${objekt.member} ${objekt.season} ${objekt.collection_code} Token ${objekt.external_token_id}`">
    <div class="tile-image-frame">
      <img
        v-if="!imageFailed"
        :src="objekt.image_url"
        :alt="`${objekt.member} ${objekt.season} ${objekt.collection_code} 卡片正面`"
        width="1942"
        height="3000"
        loading="lazy"
        decoding="async"
        @error="imageFailed = true"
      >
      <p v-else class="tile-image-error">圖片暫時無法載入</p>
      <span class="tile-class">{{ objekt.class_name }}</span>
    </div>
    <div class="tile-information">
      <p class="tile-season">{{ objekt.season }}</p>
      <div class="tile-title"><h2>{{ objekt.member }}</h2><span>{{ objekt.collection_code }}</span></div>
      <p class="tile-token">Token ID <span>{{ objekt.external_token_id }}</span></p>
      <a
        class="tile-source"
        :href="`https://api.cosmo.fans/bff/v3/objekts/nft-metadata/${objekt.external_token_id}`"
        target="_blank"
        rel="noopener noreferrer"
        :aria-label="`查看 Token ${objekt.external_token_id} 的官方資料`"
      >官方資料</a>
    </div>
  </article>
</template>
