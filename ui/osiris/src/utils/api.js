// Cliente de la API de Pythia.
//
// En desarrollo, Vite hace de proxy de /api hacia 127.0.0.1:8088 (ver
// vite.config.js). En producción se sirve el build detrás de la propia API,
// así que la misma ruta relativa vale en ambos casos.

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

// Si el servidor tiene API_TOKEN configurado, hay que proporcionarlo.
const TOKEN = import.meta.env.VITE_API_TOKEN ?? ''

function headers(extra = {}) {
  const h = { ...extra }
  if (TOKEN) h.Authorization = `Bearer ${TOKEN}`
  return h
}

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: headers(options.headers),
  })

  if (!response.ok) {
    // La API devuelve {error, detail} en sus fallos propios y {detail} en los
    // de validación de FastAPI. Se intenta sacar algo legible de ambos.
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      detail = body.detail ?? body.error ?? detail
      if (typeof detail !== 'string') detail = JSON.stringify(detail)
    } catch {
      // Respuesta sin JSON: nos quedamos con el código.
    }
    throw new Error(detail)
  }

  return response.json()
}

export const api = {
  health: () => request('/health'),
  view: (limit = 12) => request(`/agent/view?limit=${limit}`),
  events: ({ source, minSalience = 0, limit = 40 } = {}) => {
    const params = new URLSearchParams({ min_salience: minSalience, limit })
    if (source) params.set('source', source)
    return request(`/agent/events?${params}`)
  },
  predictions: (limit = 10) => request(`/predictions?limit=${limit}`),
  predict: (query, horizon) =>
    request('/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, horizon }),
    }),
  scorecard: () => request('/scorecard'),
}

/**
 * Suscripción al flujo SSE de estado.
 *
 * EventSource no admite cabeceras, así que con API_TOKEN configurado hay que
 * pasarlo por query string. Devuelve la función para cancelar.
 */
export function subscribeState(onUpdate, onError) {
  const url = TOKEN ? `${BASE}/state/stream?token=${encodeURIComponent(TOKEN)}` : `${BASE}/state/stream`
  const source = new EventSource(url)

  source.addEventListener('update', (event) => {
    try {
      onUpdate(JSON.parse(event.data))
    } catch (err) {
      onError?.(err)
    }
  })
  // El navegador reconecta solo; solo se avisa para poder mostrarlo en la UI.
  source.onerror = () => onError?.(new Error('conexión con el flujo interrumpida'))

  return () => source.close()
}
