export default defineNuxtConfig({
  compatibilityDate: '2026-11-19',
  // 圖鑑由瀏覽器查詢本機 API；目前採客戶端渲染。
  ssr: false,
  devtools: { enabled: false },
  telemetry: false,
  routeRules: {
    '/api/collections/**': { proxy: 'http://127.0.0.1:8000/collections/**' },
  },
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      htmlAttrs: { lang: 'zh-Hant' },
      title: '個人圖鑑 | COSMO Collector Copilot',
      meta: [
        { name: 'description', content: '輸入 COSMO 暱稱，讀取目前持有的 Objekt 收藏與官方卡片資訊。' },
      ],
    },
  },
})
