import { defineStore } from 'pinia'

export type SignalView = 'list' | 'due'

const STORAGE_KEY = 'signal-view-state'

type Persisted = {
  view: SignalView
  selectedCode: string
}

function restore(): Persisted {
  const fallback: Persisted = { view: 'list', selectedCode: '' }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return fallback
    }
    const parsed = JSON.parse(raw) as Partial<Persisted>
    return {
      view: parsed.view === 'due' ? 'due' : 'list',
      selectedCode: typeof parsed.selectedCode === 'string' ? parsed.selectedCode : '',
    }
  } catch {
    return fallback
  }
}

/**信号机页面的视图与选中状态：切走再回来、整页刷新后都要保持一致。*/
export const useSignalViewStore = defineStore('signal-view', {
  state: () => {
    const saved = restore()
    return {
      activeView: saved.view as SignalView,
      selectedCode: saved.selectedCode,
    }
  },
  actions: {
    setView(view: SignalView) {
      this.activeView = view
      this.persist()
    },
    select(code: string) {
      this.selectedCode = code
      this.persist()
    },
    persist() {
      const payload: Persisted = { view: this.activeView, selectedCode: this.selectedCode }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
      } catch {
        // 存储不可用时仅保留内存中的状态，不影响页面使用
      }
    },
  },
})
