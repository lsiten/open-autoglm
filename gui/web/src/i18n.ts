import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import zh from './locales/zh.json'
import ja from './locales/ja.json'
import ko from './locales/ko.json'

const i18n = createI18n({
  legacy: false, // Use Composition API mode
  locale: navigator.language.startsWith('zh') ? 'zh' : 'en', // Default to browser language
  fallbackLocale: 'en',
  messages: {
    en,
    zh,
    ja,
    ko
  }
})

export default i18n
