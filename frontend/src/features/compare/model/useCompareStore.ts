import { create } from 'zustand'

interface CompareState {
  modificationIds: number[]
  addId: (id: number) => void
  setIds: (ids: number[]) => void
  removeId: (id: number) => void
  clear: () => void
}

const STORAGE_KEY = 'tco_compare_ids'
const MAX_COMPARE_ITEMS = 3

function loadInitial(): number[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as number[]
    return parsed.filter((item): item is number => Number.isInteger(item)).slice(0, MAX_COMPARE_ITEMS)
  } catch {
    return []
  }
}

export const useCompareStore = create<CompareState>((set) => ({
  modificationIds: loadInitial(),
  addId: (id) =>
    set((state) => {
      if (state.modificationIds.includes(id)) {
        return state
      }
      if (state.modificationIds.length >= MAX_COMPARE_ITEMS) {
        return state
      }
      return { modificationIds: [...state.modificationIds, id] }
    }),
  setIds: (ids) =>
    set({
      modificationIds: ids
        .filter((id): id is number => Number.isInteger(id))
        .filter((id, index, arr) => arr.indexOf(id) === index)
        .slice(0, MAX_COMPARE_ITEMS),
    }),
  removeId: (id) =>
    set((state) => ({ modificationIds: state.modificationIds.filter((value) => value !== id) })),
  clear: () => set({ modificationIds: [] }),
}))

useCompareStore.subscribe((state) => {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state.modificationIds))
})
