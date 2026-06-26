'use client'

import { useQuery } from '@tanstack/react-query'
import { indicatorsApi, factorsApi } from '@/lib/api'

export function useIndicatorCatalog() {
  return useQuery({
    queryKey: ['indicators', 'catalog'],
    queryFn: () => indicatorsApi.getCatalog(),
    staleTime: 30 * 60 * 1000, // 30 minutes
  })
}

export function useIndicatorHistory(codes: string[], startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: ['indicators', 'history', codes, startDate, endDate],
    queryFn: () => indicatorsApi.getHistory(codes, startDate, endDate),
    enabled: codes.length > 0,
    staleTime: 5 * 60 * 1000,
  })
}

export function useFactorDecomposition(code: string, startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: ['factors', 'decomposition', code, startDate, endDate],
    queryFn: () => factorsApi.getDecomposition(code, startDate, endDate),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  })
}
