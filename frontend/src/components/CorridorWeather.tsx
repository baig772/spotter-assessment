import { useEffect, useState } from 'react'
import type { FeatureCollection, Polygon } from 'geojson'
import type { Map as MapboxMap, GeoJSONSource } from 'mapbox-gl'
import { getCorridorWeather } from '../api/corridor'
import type { CorridorResponse } from '../api/corridor'
import { riskColors } from '../lib/mapData'

interface Props {
    map: MapboxMap
    planId: string
}

const SOURCE_ID = 'corridor-weather-grid'
const LAYER_ID = 'corridor-weather-fill'

export default function CorridorWeather({ map, planId }: Props) {
    const [data, setData] = useState<CorridorResponse | null>(null)
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(true)
    const [hour, setHour] = useState(0)
    const [visible, setVisible] = useState(true)
    const [attempt, setAttempt] = useState(0)

    useEffect(() => {
        const controller = new AbortController()
        let active = true
        let timedOut = false

        const timeout = window.setTimeout(() => {
            timedOut = true
            controller.abort()
        }, 150_000)

        getCorridorWeather(planId, controller.signal)
            .then((response) => {
                if (!active) return
                setData(response)
                setError('')
            })
            .catch((caught: unknown) => {
                if (!active) return

                if (timedOut) {
                    setError('Corridor weather timed out. Please retry.')
                } else {
                    setError(
                        caught instanceof Error
                            ? caught.message
                            : 'Could not load corridor weather.',
                    )
                }
            })
            .finally(() => {
                window.clearTimeout(timeout)
                if (active) setLoading(false)
            })

        return () => {
            active = false
            window.clearTimeout(timeout)
            controller.abort()
        }
    }, [planId, attempt])

    useEffect(() => {
        if (!data || !map.getLayer('route-backgrounds')) return

        const collection: FeatureCollection<Polygon> = {
            type: 'FeatureCollection',
            features: data.points.map((point) => {
                const sample = point.forecasts[hour]

                return {
                    type: 'Feature',
                    id: point.id,
                    properties: {
                        color: riskColors[sample.severity],
                        status: sample.status,
                    },
                    geometry: point.geometry,
                }
            }),
        }

        const existingSource = map.getSource(SOURCE_ID) as
            | GeoJSONSource
            | undefined

        if (existingSource) {
            existingSource.setData(collection)
        } else {
            map.addSource(SOURCE_ID, {
                type: 'geojson',
                data: collection,
            })
        }

        if (!map.getLayer(LAYER_ID)) {
            map.addLayer(
                {
                    id: LAYER_ID,
                    type: 'fill',
                    source: SOURCE_ID,
                    paint: {
                        'fill-color': ['get', 'color'],
                        'fill-opacity': [
                            'case',
                            ['==', ['get', 'status'], 'unknown'],
                            0.25,
                            0.35,
                        ],
                        'fill-antialias': false,
                    },
                },
                'route-backgrounds',
            )
        }

        map.setLayoutProperty(
            LAYER_ID,
            'visibility',
            visible ? 'visible' : 'none',
        )

        // Sources and layers belong to the map and are removed when it is destroyed.
    }, [map, data, hour, visible])

    function retry() {
        setLoading(true)
        setError('')
        setAttempt((value) => value + 1)
    }

    if (loading) {
        return (
            <section className="forecast-controls" aria-busy="true">
                <h3>Corridor weather</h3>
                <p role="status">Loading the next 48 hours of corridor weather…</p>
            </section>
        )
    }

    if (error || !data) {
        return (
            <section className="forecast-controls">
                <h3>Corridor weather</h3>
                <p role="alert" className="error-message">
                    {error || 'Weather unavailable.'}
                </p>
                <button type="button" onClick={retry}>Retry weather</button>
            </section>
        )
    }

    const selectedTime = new Date(data.times[hour]).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZoneName: 'short',
    })

    const available = data.points.filter(
        (point) => point.forecasts[hour].status === 'available',
    ).length

    return (
        <section className="forecast-controls" aria-label="Corridor forecast">
            <div className="forecast-heading">
                <h3>Corridor weather</h3>
                <label className="forecast-toggle">
                    <input
                        type="checkbox"
                        checked={visible}
                        onChange={(event) => setVisible(event.target.checked)}
                    />
                    Show heatmap
                </label>
            </div>

            <label htmlFor="forecast-hour">
                Forecast hour: +{hour}h
            </label>

            <p className="forecast-timestamp">
                <time dateTime={data.times[hour]}>{selectedTime}</time>
            </p>

            <input
                id="forecast-hour"
                className="forecast-slider"
                type="range"
                min="0"
                max="48"
                step="1"
                value={hour}
                aria-valuetext={`Hour ${hour}: ${selectedTime}`}
                onChange={(event) => setHour(Number(event.target.value))}
            />

            <div className="forecast-range-labels" aria-hidden="true">
                <span>+0h</span>
                <span>+24h</span>
                <span>+48h</span>
            </div>

            <p className="help">
                Hour 0 is the start of the current UTC hour when this forecast was
                requested. Times above are displayed in your browser’s time zone.
            </p>

            <p className="help">
                Grid colors show sampled weather risk for the submitted load.
                Route lines and checkpoint popups retain arrival-time risk.
                Colors use the risk legend below the map.
            </p>

            <p className="help">
                {available}/{data.points.length} cells available · approximately{' '}
                {(data.grid_spacing_meters / 1000).toFixed(0)} km spacing.
                Gray cells mean unknown weather; unshaded areas are not assessed.
            </p>

            {data.warnings.map((warning) => (
                <p className="notice" key={warning}>{warning}</p>
            ))}
        </section>
    )
}