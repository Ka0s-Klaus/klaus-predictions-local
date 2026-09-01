import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

/**
 * Globo con los eventos georreferenciados.
 *
 * Los marcadores comparten color y codifican la relevancia con el tamaño. Un
 * tono por dominio parecería más informativo, pero sobre una esfera cualquier
 * par de marcadores puede acabar contiguo, y con más de tres categorías esas
 * combinaciones dejan de ser distinguibles bajo daltonismo. La identidad va en
 * el tooltip, que es donde se puede leer sin ambigüedad.
 */
const RADIUS = 1
const SERIES_1 = 0x3987e5
const SPHERE = 0x1f2a38
const WIREFRAME = 0x2c3a4a

function toCartesian(latitude, longitude, radius = RADIUS) {
  const phi = (90 - latitude) * (Math.PI / 180)
  const theta = (longitude + 180) * (Math.PI / 180)
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  )
}

export default function Globe3D({ events = [] }) {
  const mountRef = useRef(null)
  const sceneRef = useRef(null)
  const [hover, setHover] = useState(null)

  // Montaje de la escena. Se hace una sola vez: recrear el renderer en cada
  // cambio de eventos filtraría contextos WebGL hasta que el navegador
  // empieza a descartarlos.
  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return undefined

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100)
    camera.position.z = 3.2

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)

    const globe = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS, 48, 48),
      new THREE.MeshBasicMaterial({ color: SPHERE }),
    )
    scene.add(globe)

    const grid = new THREE.LineSegments(
      new THREE.WireframeGeometry(new THREE.SphereGeometry(RADIUS * 1.001, 18, 12)),
      new THREE.LineBasicMaterial({ color: WIREFRAME, transparent: true, opacity: 0.5 }),
    )
    globe.add(grid)

    const markers = new THREE.Group()
    globe.add(markers)

    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    let pointerActive = false

    function resize() {
      const size = mount.clientWidth
      if (!size) return
      renderer.setSize(size, size, false)
      camera.aspect = 1
      camera.updateProjectionMatrix()
    }
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(mount)

    function onPointerMove(event) {
      const rect = renderer.domElement.getBoundingClientRect()
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
      pointerActive = true
    }
    function onPointerLeave() {
      pointerActive = false
      setHover(null)
    }
    renderer.domElement.addEventListener('pointermove', onPointerMove)
    renderer.domElement.addEventListener('pointerleave', onPointerLeave)

    let frame = 0
    let paused = false
    function animate() {
      frame = requestAnimationFrame(animate)
      if (!paused) globe.rotation.y += 0.0012

      if (pointerActive && markers.children.length) {
        raycaster.setFromCamera(pointer, camera)
        const hit = raycaster.intersectObjects(markers.children, false)[0]
        // Girar mientras se lee el tooltip haría imposible seguir el marcador.
        paused = Boolean(hit)
        setHover(
          hit
            ? {
                data: hit.object.userData,
                x: ((pointer.x + 1) / 2) * mount.clientWidth,
                y: ((1 - pointer.y) / 2) * mount.clientHeight,
              }
            : null,
        )
      } else {
        paused = false
      }

      renderer.render(scene, camera)
    }
    animate()

    sceneRef.current = { markers }

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      renderer.domElement.removeEventListener('pointermove', onPointerMove)
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave)
      // Sin liberar geometrías y materiales, three.js los deja en la GPU.
      scene.traverse((object) => {
        object.geometry?.dispose()
        object.material?.dispose()
      })
      renderer.dispose()
      mount.removeChild(renderer.domElement)
      sceneRef.current = null
    }
  }, [])

  // Los marcadores se reconstruyen aparte, sin tocar el renderer.
  useEffect(() => {
    const group = sceneRef.current?.markers
    if (!group) return

    for (const child of [...group.children]) {
      group.remove(child)
      child.geometry.dispose()
      child.material.dispose()
    }

    for (const event of events) {
      if (event.latitude == null || event.longitude == null) continue

      const salience = event.salience ?? 0.5
      const marker = new THREE.Mesh(
        // El tamaño codifica la relevancia; mínimo de 8px equivalentes para
        // que siga siendo un objetivo alcanzable con el ratón.
        new THREE.SphereGeometry(0.016 + salience * 0.026, 10, 10),
        new THREE.MeshBasicMaterial({ color: SERIES_1 }),
      )
      marker.position.copy(toCartesian(event.latitude, event.longitude, RADIUS * 1.02))
      marker.userData = event
      group.add(marker)
    }
  }, [events])

  const located = events.filter((e) => e.latitude != null && e.longitude != null)

  return (
    <section className="panel">
      <h2>Globo</h2>
      <p className="hint">
        {located.length} de {events.length} eventos tienen coordenadas. El tamaño del marcador
        es su relevancia.
      </p>
      <div className="globe" ref={mountRef}>
        {hover && (
          <div
            className="globe-tooltip"
            style={{
              left: Math.min(hover.x + 12, 300),
              top: Math.max(hover.y - 12, 0),
            }}
          >
            <div className="src">
              {hover.data.source} · relevancia {(hover.data.salience ?? 0).toFixed(2)}
            </div>
            <div>{hover.data.title}</div>
          </div>
        )}
      </div>
    </section>
  )
}
