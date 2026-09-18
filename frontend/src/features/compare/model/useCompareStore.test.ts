import { describe, expect, it } from 'vitest'

import { useCompareStore } from './useCompareStore'

describe('useCompareStore', () => {
  it('adds unique ids and limits size to 3', () => {
    useCompareStore.setState({ modificationIds: [] })

    useCompareStore.getState().addId(101)
    useCompareStore.getState().addId(101)
    useCompareStore.getState().addId(102)
    useCompareStore.getState().addId(103)
    useCompareStore.getState().addId(104)

    expect(useCompareStore.getState().modificationIds).toEqual([101, 102, 103])
  })

  it('removes ids and clears all', () => {
    useCompareStore.setState({ modificationIds: [101, 102, 103] })

    useCompareStore.getState().removeId(102)
    expect(useCompareStore.getState().modificationIds).toEqual([101, 103])

    useCompareStore.getState().clear()
    expect(useCompareStore.getState().modificationIds).toEqual([])
  })
})
