/**
 * Fila de indicadores.
 *
 * Cuando la historia es un número, el número es el gráfico: un tile, no una
 * barra de un solo dato ni un donut de dos porciones.
 */
export default function Dashboard({ health, stream }) {
  const feeds = health?.feeds
  const eventos = stream?.total_events

  const tiles = [
    {
      label: 'Eventos',
      value: eventos ?? '—',
      sub: stream ? `${stream.feeds_active} fuentes con datos` : 'sin conexión al flujo',
    },
    {
      label: 'Fuentes',
      value: feeds ? `${feeds.implemented}` : '—',
      sub: feeds ? `de ${feeds.total} en catálogo` : '',
    },
    {
      label: 'Agentes',
      value: health?.agents ?? '—',
      sub: 'enjambre MiroFish',
    },
    {
      label: 'Horizontes',
      value: health?.horizons?.length ?? '—',
      sub: health?.horizons?.join(' · ') ?? '',
    },
    {
      label: 'En marcha',
      value: formatUptime(health?.uptime_seconds),
      sub: health ? `v${health.version}` : '',
    },
  ]

  return (
    <div className="tiles">
      {tiles.map((tile) => (
        <div className="tile" key={tile.label}>
          <div className="label">{tile.label}</div>
          <div className="value">{tile.value}</div>
          {tile.sub && <div className="sub">{tile.sub}</div>}
        </div>
      ))}
    </div>
  )
}

function formatUptime(seconds) {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}
