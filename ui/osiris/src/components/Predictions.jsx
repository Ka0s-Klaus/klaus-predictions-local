import { useState, useRef, useEffect } from 'react'

import { api, predictStream } from '../utils/api.js'

const HORIZONS = ['24h', 'week', 'month', 'year']

/**
 * Lanza una predicción y muestra el voto de cada agente.
 *
 * Los siete agentes son una sola serie —una medida, siete categorías—, así que
 * comparten color. Un tono distinto por barra duplicaría en color lo que la
 * longitud ya comunica y gastaría el único canal libre que queda.
 */
export default function Predictions({ threshold = 0.65 }) {
  const [query, setQuery] = useState('¿Cuáles son las principales anomalías globales?')
  const [horizon, setHorizon] = useState('24h')
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [tabla, setTabla] = useState(false)
  const [progress, setProgress] = useState(null)
  const cancelRef = useRef(null)

  async function submit(event) {
    event.preventDefault()
    setPending(true)
    setError(null)
    setResult(null)
    setProgress({ agents: 0 })

    cancelRef.current = predictStream(
      query,
      horizon,
      (event) => {
        if (event.event === 'started') {
          setProgress({ agents: event.data.agents, status: 'Iniciando…' })
        } else if (event.event === 'completed') {
          setProgress((prev) => ({ ...prev, status: 'Generando respuesta…' }))
        } else if (event.event === 'result') {
          setResult(event.data)
          setProgress(null)
          setPending(false)
        } else if (event.event === 'error') {
          setError(event.data.message || 'Error desconocido')
          setProgress(null)
          setPending(false)
        }
      },
      (err) => {
        setError(err.message)
        setProgress(null)
        setPending(false)
      }
    )
  }

  function cancelPrediction() {
    if (cancelRef.current) {
      cancelRef.current()
      cancelRef.current = null
    }
    setPending(false)
    setProgress(null)
  }

  useEffect(() => {
    return () => {
      if (cancelRef.current) {
        cancelRef.current()
      }
    }
  }, [])

  const votes = result ? Object.entries(result.agent_votes).sort((a, b) => b[1] - a[1]) : []

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Predicción del enjambre</h2>
          <p className="hint">
            Los siete agentes se resuelven en una sola llamada al modelo.
          </p>
        </div>
        {result && (
          <button className="toggle" onClick={() => setTabla((v) => !v)}>
            {tabla ? 'Ver barras' : 'Ver tabla'}
          </button>
        )}
      </div>

      <form className="ask" onSubmit={submit}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="¿Qué quieres preguntar?"
          required
          maxLength={2000}
        />
        <div className="row">
          <select value={horizon} onChange={(e) => setHorizon(e.target.value)} disabled={pending}>
            {HORIZONS.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
          <button type="submit" disabled={pending}>
            {pending ? 'Razonando…' : 'Predecir'}
          </button>
          {pending && (
            <button type="button" onClick={cancelPrediction} className="secondary">
              Cancelar
            </button>
          )}
        </div>
      </form>

      {progress && (
        <div className="notice" style={{ backgroundColor: '#f0f4ff', padding: '16px', borderRadius: '4px' }}>
          <div style={{ marginBottom: '12px', fontWeight: 'bold' }}>
            🔄 {progress.status || `Procesando ${progress.agents} agentes…`}
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '8px',
            }}
          >
            {Array.from({ length: progress.agents }).map((_, i) => (
              <div key={i} style={{ textAlign: 'center', fontSize: '12px' }}>
                <div
                  style={{
                    width: '100%',
                    height: '4px',
                    backgroundColor: '#e0e0e0',
                    borderRadius: '2px',
                    overflow: 'hidden',
                    marginBottom: '4px',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      backgroundColor: '#6366f1',
                      animation: 'pulse 1.5s ease-in-out infinite',
                      width: '100%',
                    }}
                  />
                </div>
                <span>Agente {i + 1}</span>
              </div>
            ))}
          </div>
          <style>{`
            @keyframes pulse {
              0%, 100% { opacity: 0.3; }
              50% { opacity: 1; }
            }
          `}</style>
        </div>
      )}

      {pending && !progress && (
        <div className="notice">
          Con un modelo de 7B en CPU esto tarda <strong>minutos</strong>, no segundos. Ver
          docs/HARDWARE.md.
        </div>
      )}

      {error && <div className="notice error">{error}</div>}

      {result && (
        <div className="verdict">
          <p>{result.prediction}</p>

          <div className="tiles" style={{ marginBottom: 16 }}>
            <div className="tile">
              <div className="label">Confianza</div>
              <div className="value">{(result.confidence * 100).toFixed(0)}%</div>
              <div className="sub">
                {result.meets_threshold ? 'supera el umbral' : 'por debajo del umbral'}
              </div>
            </div>
            <div className="tile">
              <div className="label">Discrepancia</div>
              <div className="value">{result.dissent.toFixed(2)}</div>
              <div className="sub">desviación entre agentes</div>
            </div>
            <div className="tile">
              <div className="label">Latencia</div>
              <div className="value">{(result.latency_ms / 1000).toFixed(1)}s</div>
              <div className="sub">{result.sources_used.join(', ') || 'sin fuentes citadas'}</div>
            </div>
          </div>

          {tabla ? (
            <table>
              <thead>
                <tr>
                  <th>Agente</th>
                  <th className="num">Confianza</th>
                </tr>
              </thead>
              <tbody>
                {votes.map(([name, value]) => (
                  <tr key={name}>
                    <td>{name.replace(/_/g, ' ')}</td>
                    <td className="num">{value.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="bars">
              {votes.map(([name, value]) => (
                <div className="bar-row" key={name}>
                  <span className="name">{name.replace(/_/g, ' ')}</span>
                  <span className="bar-track">
                    <span className="bar-fill" style={{ width: `${value * 100}%` }} />
                    {/* Umbral de consenso: referencia recesiva, no un dato. */}
                    <span
                      className="bar-threshold"
                      style={{ left: `${threshold * 100}%` }}
                      title={`Umbral de consenso ${threshold}`}
                    />
                  </span>
                  <span className="value">{value.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
