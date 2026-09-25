import { defineStore } from 'pinia'

const STORAGE_KEY = 'signal-view-state'
const VALID_VIEWS = ['list', 'due'] as const
export type SignalView = (typeof VALID_VIEWS)[number]

interface PersistedState {
  view: SignalView
  selectedCode: string
  listKeyword: string
}

/** 信号机页面状态：当前视图、按设备编号记住的选中项、列表定位用的检索词。

 * 除了放在 Pinia 里，还同步到 sessionStorage，切走再回来（组件重建）
 * 甚至刷新页面后视图与选中位置都不丢。
 */
function restore(): PersistedState {
  const fallback: PersistedState = { view: 'list', selectedCode: '', listKeyword: '' }
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return fallback
    }
    const parsed = JSON.parse(raw) as Partial<PersistedState>
    return {
      view: VALID_VIEWS.includes(parsed.view as SignalView)
        ? (parsed.view as SignalView)
        : fallback.view,
      selectedCode: typeof parsed.selectedCode === 'string' ? parsed.selectedCode : '',
      listKeyword: typeof parsed.listKeyword === 'string' ? parsed.listKeyword : '',
    }
  } catch {
    return fallback
  }
}

export const useSignalViewStore = defineStore('signalView', {
  state: () => restore(),
  actions: {
    persist() {
      const snapshot: PersistedState = {
        view: this.view,
        selectedCode: this.selectedCode,
        listKeyword: this.listKeyword,
      }
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
      } catch {
        // 隐私模式等场景写不进 storage 时静默降级，仅保留内存态
      }
    },
    setView(view: SignalView) {
      this.view = view
      this.persist()
    },
    select(code: string) {
      this.selectedCode = code
      this.persist()
    },
    setListKeyword(keyword: string) {
      this.listKeyword = keyword
      this.persist()
    },
  },
})
