/**
 * API client for dashboard backend
 */
const API_BASE = '/api/v1'

async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }

  return response.json()
}

// Indicator APIs
export const indicatorsApi = {
  getCatalog: () => fetchApi('/indicators/catalog'),
  getHistory: (codes: string[], startDate?: string, endDate?: string) => {
    const params = new URLSearchParams()
    params.append('codes', codes.join(','))
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    return fetchApi(`/indicators/history?${params}`)
  },
  getLatest: () => fetchApi('/indicators/latest'),
}

// Factor APIs
export const factorsApi = {
  getDecomposition: (code: string, startDate?: string, endDate?: string) => {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    return fetchApi(`/factors/decomposition/${code}?${params}`)
  },
  getLatest: () => fetchApi('/factors/latest'),
}

// State APIs
export const statesApi = {
  getHistory: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    return fetchApi(`/states/history?${params}`)
  },
  getLatest: () => fetchApi('/states/latest'),
  getByDate: (date: string) => fetchApi(`/states/${date}`),
  getRegimeTransitions: () => fetchApi('/states/regime-transitions'),
}

// Analysis APIs
export const analysisApi = {
  getNarrative: (date: string) => fetchApi(`/analysis/narrative/${date}`),
}
