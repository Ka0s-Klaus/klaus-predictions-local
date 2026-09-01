import { useState } from 'react'

/**
 * Eventos ingeridos, ordenados por relevancia.
 *
 * El medidor codifica la magnitud con la anchura y mantiene el color
 * constante: teñirlo también por valor repetiría en color lo que la longitud
 * ya dice.
 */
export default function FeedsList({ events, error }) {
  const [tabla, setTabla] = useState(false)

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Señales en vivo</h2>
          <p className="hint">Relevancia de 0 a 1, calculada por cada fuente.</p>
        </div>
        <button className="toggle" onClick={() => setTabla((v) => !v)}>
          {tabla ? 'Ver lista' : 'Ver tabla'}
        </button>
      </div>

      {error && <div className="notice error">No se pudieron cargar los eventos: {error}</div>}

      {!events?.length && !error && <div className="empty">Sin eventos todavía.</div>}

      {events?.length > 0 &&
        (tabla ? (
          <table>
            <thead>
              <tr>
                <th>Fuente</th>
                <th>Evento</th>
                <th className="num">Relevancia</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={`${e.source}-${i}`}>
                  <td>{e.source}</td>
                  <td>{e.title}</td>
                  <td className="num">{e.salience.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="feeds">
            {events.map((e, i) => (
              <div className="feed" key={`${e.source}-${i}`} title={e.title}>
                <span className="source">{e.source}</span>
                <span className="title">
                  {e.url ? (
                    <a href={e.url} target="_blank" rel="noreferrer noopener">
                      {e.title}
                    </a>
                  ) : (
                    e.title
                  )}
                </span>
                <span
                  className="meter"
                  role="img"
                  aria-label={`Relevancia ${e.salience.toFixed(2)} de 1`}
                >
                  <i style={{ width: `${Math.round(e.salience * 100)}%` }} />
                </span>
              </div>
            ))}
          </div>
        ))}
    </section>
  )
}
