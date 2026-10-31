import { useEffect, useRef, useState } from 'react'
import mapboxgl from 'mapbox-gl'
import type { Checkpoint, RouteOption } from '../api/routes'
import { createMapData, riskColors } from '../lib/mapData'
import 'mapbox-gl/dist/mapbox-gl.css'

interface Props {
    routes: RouteOption[]
    selectedId: string
    onSelectRoute: (routeId: string) => void
}

function checkpointContent(checkpoint: Checkpoint) {
    const container = document.createElement('div')
    container.className = 'checkpoint-popup'

    const heading = document.createElement('strong')
    heading.textContent =
        `${(checkpoint.distance_from_start_meters / 1609.344).toFixed(1)} miles` +
        ` · ${checkpoint.risk.severity.replace('_', ' ').toUpperCase()}`

    container.append(heading)

    const rows = [
        `ETA: ${new Date(checkpoint.arrival_time).toLocaleString(undefined, {
            timeZoneName: 'short',
        })}`,
    ]

    if (checkpoint.weather.status === 'available') {
        rows.push(
            `Wind: ${checkpoint.weather.wind_mph?.toFixed(1)} mph`,
            `Rain: ${checkpoint.weather.rain_inches_per_hour?.toFixed(3)} in/hr`,
            `Snow: ${checkpoint.weather.snow_inches_per_hour?.toFixed(3)} in/hr`,
        )
    } else {
        rows.push(checkpoint.weather.reason || 'Weather unavailable.')
    }

    rows.push(...checkpoint.risk.reasons)

    for (const text of rows) {
        const paragraph = document.createElement('p')
        paragraph.textContent = text
        container.append(paragraph)
    }

    return container
}

export default function RouteMap({
    routes,
    selectedId,
    onSelectRoute,
}: Props) {
    const containerRef = useRef<HTMLDivElement>(null)
    const mapRef = useRef<mapboxgl.Map | null>(null)
    const popupRef = useRef<mapboxgl.Popup | null>(null)

    const [ready, setReady] = useState(false)
    const [mapError, setMapError] = useState('')

    const token = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN as string | undefined
    const selectedRoute = routes.find((route) => route.id === selectedId)

    useEffect(() => {
        if (!containerRef.current || !token) return

        const map = new mapboxgl.Map({
            container: containerRef.current,
            accessToken: token,
            style: 'mapbox://styles/mapbox/light-v11',
            center: routes[0]?.geometry.coordinates[0] || [-98, 39],
            zoom: 4,
        })

        mapRef.current = map
        map.addControl(new mapboxgl.NavigationControl(), 'top-right')

        const observer = new ResizeObserver(() => map.resize())
        observer.observe(containerRef.current)

        map.on('error', () => {
            setMapError(
                'Some map resources failed to load. Check your token, allowed URLs, and connection.',
            )
        })

        map.on('load', () => {
            const data = createMapData(routes)

            map.addSource('routes', {
                type: 'geojson',
                data: data.lines,
            })

            map.addSource('risks', {
                type: 'geojson',
                data: data.risks,
            })

            map.addSource('checkpoints', {
                type: 'geojson',
                data: data.points,
            })

            map.addLayer({
                id: 'route-backgrounds',
                type: 'line',
                source: 'routes',
                paint: {
                    'line-color': '#516780',
                    'line-width': 9,
                },
                layout: {
                    'line-cap': 'round',
                    'line-join': 'round',
                },
            })

            map.addLayer({
                id: 'all-risks',
                type: 'line',
                source: 'risks',
                paint: {
                    'line-color': ['get', 'color'],
                    'line-width': 4,
                    'line-opacity': 0.65,
                },
            })

            map.addLayer({
                id: 'route-hit',
                type: 'line',
                source: 'routes',
                paint: {
                    'line-width': 22,
                    'line-opacity': 0,
                },
            })

            map.addLayer({
                id: 'selected-outline',
                type: 'line',
                source: 'routes',
                filter: ['==', 'routeId', ''],
                paint: {
                    'line-color': '#172b3a',
                    'line-width': 11,
                },
                layout: {
                    'line-cap': 'round',
                    'line-join': 'round',
                },
            })

            map.addLayer({
                id: 'selected-risk',
                type: 'line',
                source: 'risks',
                filter: ['==', 'routeId', ''],
                paint: {
                    'line-color': ['get', 'color'],
                    'line-width': 7,
                },
                layout: {
                    'line-cap': 'round',
                    'line-join': 'round',
                },
            })

            map.addLayer({
                id: 'checkpoint-points',
                type: 'circle',
                source: 'checkpoints',
                filter: ['==', 'routeId', ''],
                paint: {
                    'circle-color': ['get', 'color'],
                    'circle-radius': 6,
                    'circle-stroke-color': '#ffffff',
                    'circle-stroke-width': 2,
                },
            })

            map.addLayer({
                id: 'checkpoint-hit',
                type: 'circle',
                source: 'checkpoints',
                filter: ['==', 'routeId', ''],
                paint: {
                    'circle-radius': 16,
                    'circle-opacity': 0,
                },
            })

            const bounds = new mapboxgl.LngLatBounds()

            for (const route of routes) {
                for (const coordinate of route.geometry.coordinates) {
                    bounds.extend(coordinate)
                }
            }

            if (!bounds.isEmpty()) {
                map.fitBounds(bounds, {
                    padding: 50,
                    duration: 0,
                    maxZoom: 12,
                })
            }

            map.on('click', (event) => {
                const checkpoints = map.queryRenderedFeatures(event.point, {
                    layers: ['checkpoint-hit'],
                })

                const point = checkpoints[0]

                if (point) {
                    const route = routes.find(
                        (item) => item.id === point.properties?.routeId,
                    )

                    const checkpoint = route?.checkpoints.find(
                        (item) => item.id === point.properties?.checkpointId,
                    )

                    if (checkpoint) {
                        popupRef.current?.remove()

                        popupRef.current = new mapboxgl.Popup({
                            maxWidth: '300px',
                        })
                            .setLngLat(checkpoint.coordinates)
                            .setDOMContent(checkpointContent(checkpoint))
                            .addTo(map)
                    }

                    return
                }

                const hits = map.queryRenderedFeatures(event.point, {
                    layers: ['route-hit'],
                })

                const routeId = hits[0]?.properties?.routeId

                if (typeof routeId === 'string') {
                    onSelectRoute(routeId)
                }
            })

            for (const layer of ['route-hit', 'checkpoint-hit']) {
                map.on('mouseenter', layer, () => {
                    map.getCanvas().style.cursor = 'pointer'
                })

                map.on('mouseleave', layer, () => {
                    map.getCanvas().style.cursor = ''
                })
            }

            setReady(true)
        })

        return () => {
            observer.disconnect()
            popupRef.current?.remove()
            map.remove()
            mapRef.current = null
        }
    }, [routes, token, onSelectRoute])

    useEffect(() => {
        const map = mapRef.current

        if (!ready || !map || !map.getLayer('selected-risk')) return

        for (const layer of [
            'selected-outline',
            'selected-risk',
            'checkpoint-points',
            'checkpoint-hit',
        ]) {
            map.setFilter(layer, ['==', 'routeId', selectedId])
        }

        popupRef.current?.remove()
    }, [selectedId, ready])

    function inspectCheckpoint(id: string) {
        const checkpoint = selectedRoute?.checkpoints.find(
            (point) => point.id === id,
        )

        const map = mapRef.current

        if (!checkpoint || !map || !ready) return

        popupRef.current?.remove()

        popupRef.current = new mapboxgl.Popup({
            maxWidth: '300px',
        })
            .setLngLat(checkpoint.coordinates)
            .setDOMContent(checkpointContent(checkpoint))
            .addTo(map)

        map.easeTo({
            center: checkpoint.coordinates,
            duration: 0,
        })
    }

    if (!token) {
        return (
            <p role="alert" className="error-message">
                Add VITE_MAPBOX_ACCESS_TOKEN to frontend/.env and restart Vite.
            </p>
        )
    }

    return (
        <section className="route-map-section" aria-label="Route map">
            <div className="map-route-options" aria-label="Select a route">
                {routes.map((route) => (
                    <button
                        key={route.id}
                        type="button"
                        aria-pressed={selectedId === route.id}
                        onClick={() => onSelectRoute(route.id)}
                    >
                        {route.id}
                        {route.recommended ? ' · Recommended' : ''}
                    </button>
                ))}
            </div>

            {mapError && (
                <p role="alert" className="error-message">
                    {mapError}
                </p>
            )}

            {!ready && !mapError && (
                <p role="status">Loading map…</p>
            )}

            <div
                ref={containerRef}
                className="route-map-canvas"
                aria-label="Driving routes and weather checkpoints"
            />

            <div className="risk-legend" aria-label="Weather risk legend">
                {Object.entries(riskColors).map(([level, color]) => (
                    <span key={level}>
                        <i
                            style={{ backgroundColor: color }}
                            aria-hidden="true"
                        />
                        {level.replace('_', ' ')}
                    </span>
                ))}
            </div>

            <p className="help">
                Thick line: selected route. Dots: its checkpoints.
                ETA times use your browser’s time zone.
            </p>

            <label>
                Inspect a checkpoint
                <select
                    key={selectedId}
                    defaultValue=""
                    disabled={!ready}
                    onChange={(event) => inspectCheckpoint(event.target.value)}
                >
                    <option value="">Choose a checkpoint</option>

                    {selectedRoute?.checkpoints.map((checkpoint, index, points) => (
                        <option key={checkpoint.id} value={checkpoint.id}>
                            {index === 0
                                ? 'Start · '
                                : index === points.length - 1
                                    ? 'End · '
                                    : ''}
                            {(checkpoint.distance_from_start_meters / 1609.344).toFixed(1)} mi
                            {' · '}
                            {checkpoint.risk.severity.replace('_', ' ')}
                        </option>
                    ))}
                </select>
            </label>
        </section>
    )
}