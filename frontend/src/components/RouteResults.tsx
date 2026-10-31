import { useState } from 'react'
import type { RiskLevel, RouteOption } from '../api/routes'
import { riskColors } from '../lib/mapData'
import RouteMap from './RouteMap'

interface Props {
    routes: RouteOption[]
}

const riskLabels: Record<RiskLevel, string> = {
    low: 'Low',
    moderate: 'Moderate',
    high: 'High',
    severe: 'Severe',
    no_travel: 'No Travel',
    unknown: 'Unknown',
}

function formatDuration(seconds: number) {
    const totalMinutes = Math.round(seconds / 60)
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60

    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
}

function formatArrival(route: RouteOption) {
    const finalCheckpoint = route.checkpoints.at(-1)

    if (!finalCheckpoint) return 'Unavailable'

    return new Date(finalCheckpoint.arrival_time).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZoneName: 'short',
    })
}

function routeLabel(id: string) {
    return id.replace(/^route-/, 'Route ')
}

export default function RouteResults({ routes }: Props) {
    const [selectedId, setSelectedId] = useState(
        () => routes.find((route) => route.recommended)?.id || routes[0]?.id || '',
    )

    const orderedRoutes = [...routes].sort(
        (a, b) =>
            (a.rank ?? Number.POSITIVE_INFINITY) -
            (b.rank ?? Number.POSITIVE_INFINITY),
    )

    return (
        <section className="route-results" aria-label="Route comparison and map">
            <h3>Compare routes</h3>
            <p className="help">
                Arrival times use your browser’s time zone.
                Risk miles are estimated between weather checkpoints.
            </p>

            <div className="route-comparison-grid">
                {orderedRoutes.map((route) => {
                    const selected = route.id === selectedId
                    const summary = route.risk_summary

                    return (
                        <article
                            key={route.id}
                            className={`route-card${selected ? ' is-selected' : ''}`}
                            aria-label={routeLabel(route.id)}
                        >
                            <div className="route-card-heading">
                                <h4>{routeLabel(route.id)}</h4>

                                <span
                                    className={
                                        route.recommended
                                            ? 'route-badge recommended'
                                            : summary.eligible
                                                ? 'route-badge'
                                                : 'route-badge excluded'
                                    }
                                >
                                    {route.recommended
                                        ? 'Recommended'
                                        : summary.eligible
                                            ? `Rank ${route.rank}`
                                            : 'Excluded'}
                                </span>
                            </div>

                            <dl className="route-metrics">
                                <div>
                                    <dt>Distance</dt>
                                    <dd>
                                        {(route.distance_meters / 1609.344).toFixed(1)} mi
                                    </dd>
                                </div>
                                <div>
                                    <dt>Travel time</dt>
                                    <dd>{formatDuration(route.duration_seconds)}</dd>
                                </div>
                                <div className="metric-full">
                                    <dt>Arrival</dt>
                                    <dd>{formatArrival(route)}</dd>
                                </div>
                                <div className="metric-full">
                                    <dt>Average risk score</dt>
                                    <dd>
                                        {summary.average_risk === null
                                            ? 'Unknown'
                                            : summary.average_risk.toFixed(3)}
                                    </dd>
                                </div>
                            </dl>

                            <p className="help">
                                Distance-weighted score: Low 0, Moderate 1, High 2,
                                Severe 3, No Travel 4.
                            </p>

                            <dl className="risk-mile-list" aria-label="Miles by risk level">
                                {(Object.keys(riskLabels) as RiskLevel[]).map((level) => (
                                    <div key={level}>
                                        <dt>
                                            <i
                                                style={{ backgroundColor: riskColors[level] }}
                                                aria-hidden="true"
                                            />
                                            {riskLabels[level]}
                                        </dt>
                                        <dd>{summary.risk_miles[level].toFixed(2)} mi</dd>
                                    </div>
                                ))}
                            </dl>

                            {summary.exclusion_reasons.map((reason) => (
                                <p className="route-exclusion" key={reason}>
                                    {reason}
                                </p>
                            ))}

                            <button
                                type="button"
                                className="route-select-button"
                                aria-pressed={selected}
                                aria-label={`Select ${routeLabel(route.id)} on the map`}
                                onClick={() => setSelectedId(route.id)}
                            >
                                {selected ? 'Selected on map' : 'View on map'}
                            </button>
                        </article>
                    )
                })}
            </div>

            <p className="help" role="status">
                Selected: {routeLabel(selectedId)}.
                Selection changes the map view, not the recommendation.
            </p>

            <RouteMap
                routes={routes}
                selectedId={selectedId}
                onSelectRoute={setSelectedId}
            />
        </section>
    )
}