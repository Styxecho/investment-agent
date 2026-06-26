'use client'

import { useQuery } from '@tanstack/react-query'
import { statesApi } from '@/lib/api'

export function useLatestState() {
  return useQuery({
    queryKey: ['state', 'latest'],
    queryFn: () => statesApi.getLatest(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export function useStateByDate(date: string) {
  return useQuery({
    queryKey: ['state', date],
    queryFn: () => statesApi.getByDate(date),
    enabled: !!date,
    staleTime: 5 * 60 * 1000,
  })
}

export function useStateHistory(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: ['state', 'history', startDate, endDate],
    queryFn: () => statesApi.getHistory(startDate, endDate),
    staleTime: 5 * 60 * 1000,
  })
}

export function useRegimeTransitions() {
  return useQuery({
    queryKey: ['state', 'transitions'],
    queryFn: () => statesApi.getRegimeTransitions(),
    staleTime: 5 * 60 * 1000,
  })
}
