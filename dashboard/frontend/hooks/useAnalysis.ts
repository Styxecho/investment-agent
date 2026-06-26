'use client'

import { useQuery } from '@tanstack/react-query'
import { analysisApi } from '@/lib/api'

export function useNarrative(date: string) {
  return useQuery({
    queryKey: ['analysis', 'narrative', date],
    queryFn: () => analysisApi.getNarrative(date),
    enabled: !!date,
    staleTime: 5 * 60 * 1000,
  })
}
