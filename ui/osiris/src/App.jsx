import { useEffect, useState } from 'react'

import Dashboard from './components/Dashboard.jsx'
import FeedsList from './components/FeedsList.jsx'
import Globe3D from './components/Globe3D.jsx'
import Predictions from './components/Predictions.jsx'
import { api, subscribeState } from './utils/api.js'

export default function App() {
  const [health, setHealth] = useState(null)
  const [events, setEvents] = useState([])
  const [stream, setStream] = useState(null)
  const [error, setError] = useState(null)
  const [streamError, setStreamError] = useState(null)

  useEffect(() => {
    let vigente = true

    async function cargar() {
      try {
        const [salud, vista] = await Promise.all([api.health(), api.view(40)])
        if (!vigente) return
        setHealth(salud)
        setEvents(vista.events)
        setError(null)
      } catch (err) {
        if (vigente) setError(err.message)
      }
    }

    cargar()
    // El flujo SSE avisa de los cambios; este intervalo solo refresca la lista
    // de eventos, que el flujo no transporta entera.
    const timer = setInterval(cargar, 60_000)

    const unsubscribe = subscribeState(
      (data) => {
        setStream(data)
        setStreamError(null)
      },
      (err) => setStreamError(err.message),
    )

    return () => {
      vigente = false
      clearInterval(timer)
      unsubscribe()
    }
  }, [])

  return (
    <div className="app">
      <header className="masthead">
        <div>
          <h1>Osiris</h1>
          <div className="tagline">
            Pythia · oráculo de predicción que se ejecuta en tu propia máquina
          </div>
        </div>
        {streamError && <div className="notice">Flujo en vivo: {streamError}</div>}
      </header>

      {error && (
        <div className="notice error">
          No hay conexión con la API: {error}. ¿Está en marcha <code>python -m engine.main</code>?
        </div>
      )}

      <Dashboard health={health} stream={stream} />

      <div className="grid split">
        <Globe3D events={events} />
        <Predictions threshold={0.65} />
      </div>

      <div className="grid" style={{ marginTop: 16 }}>
        <FeedsList events={events} error={error} />
      </div>
    </div>
  )
}
