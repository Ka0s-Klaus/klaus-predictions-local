import { useState } from 'react'

import { api } from '../utils/api.js'

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

  async function submit(event) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      setResult(await api.predict(query, horizon))
    } catch (err) {
      setError(err.message)
    } finally {
      setPending(false)
    }
  }

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
          <select value={horizon} onChange={(e) => setHorizon(e.target.value)}>
            {HORIZONS.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
          <button type="submit" disabled={pending}>
            {pending ? 'Razonando…' : 'Predecir'}
          </button>
        </div>
      </form>

      {pending && (
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
