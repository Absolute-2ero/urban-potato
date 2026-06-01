import { createContext, useContext, useState, type ReactNode } from 'react'
import { translations, type Lang } from './translations'

interface LangCtx {
  lang: Lang
  t: typeof translations['en']
  toggleLang: () => void
}

const Ctx = createContext<LangCtx>({
  lang: 'en',
  t: translations.en,
  toggleLang: () => {},
})

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(
    () => (localStorage.getItem('macrobite_lang') as Lang) || 'en'
  )

  const toggleLang = () => {
    const next: Lang = lang === 'en' ? 'zh' : 'en'
    setLang(next)
    localStorage.setItem('macrobite_lang', next)
  }

  return (
    <Ctx.Provider value={{ lang, t: translations[lang], toggleLang }}>
      {children}
    </Ctx.Provider>
  )
}

export function useLang() {
  return useContext(Ctx)
}
