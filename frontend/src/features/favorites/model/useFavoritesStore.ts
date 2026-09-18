import { create } from 'zustand'

interface FavoritesState {
  modificationIds: number[]
  addId: (id: number) => void
  removeId: (id: number) => void
  toggleId: (id: number) => void
  clear: () => void
}

const STORAGE_KEY = 'tco_favorite_ids'
const MAX_FAVORITES = 100

function loadInitial(): number[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as number[]
    return parsed.filter((item): item is number => Number.isInteger(item)).slice(0, MAX_FAVORITES)
  } catch {
    return []
  }
}

export const useFavoritesStore = create<FavoritesState>((set) => ({
  modificationIds: loadInitial(),
  addId: (id) =>
    set((state) => {
      if (state.modificationIds.includes(id)) return state
      if (state.modificationIds.length >= MAX_FAVORITES) return state
      return { modificationIds: [...state.modificationIds, id] }
    }),
  removeId: (id) =>
    set((state) => ({ modificationIds: state.modificationIds.filter((value) => value !== id) })),
  toggleId: (id) =>
    set((state) =>
      state.modificationIds.includes(id)
        ? { modificationIds: state.modificationIds.filter((value) => value !== id) }
        : {
            modificationIds:
              state.modificationIds.length >= MAX_FAVORITES
                ? state.modificationIds
                : [...state.modificationIds, id],
          },
    ),
  clear: () => set({ modificationIds: [] }),
}))

useFavoritesStore.subscribe((state) => {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state.modificationIds))
})
