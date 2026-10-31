import type { Polygon } from 'geojson'
import type { Coordinates, RiskLevel } from './routes'

export interface ForecastSample {
    status: 'available' | 'unknown'
    wind_mph: number | null
    rain_inches_per_hour: number | null
    snow_inches_per_hour: number | null
    severity: RiskLevel
    score: number | null
}

export interface CorridorResponse {
    reference_time: string
    times: string[]
    load_weight_lb: string
    grid_spacing_meters: number
    corridor_radius_meters: number
    points: Array<{
        id: string
        coordinates: Coordinates
        geometry: Polygon
        forecasts: ForecastSample[]
    }>
    warnings: string[]
}

const baseUrl = (
    import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'
).replace(/\/+$/, '')

export async function getCorridorWeather(
    planId: string,
    signal: AbortSignal,
): Promise<CorridorResponse> {
    const response = await fetch(`${baseUrl}/corridor-weather/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ route_plan_id: planId }),
        signal,
    })

    const body = await response.json().catch(() => null)

    if (!response.ok) {
        throw new Error(
            typeof body?.detail === 'string'
                ? body.detail
                : `Could not load corridor weather (${response.status}).`,
        )
    }

    if (
        !Array.isArray(body?.times) ||
        body.times.length !== 49 ||
        !Array.isArray(body.points) ||
        body.points.length === 0 ||
        body.points.some(
            (point: CorridorResponse['points'][number]) =>
                point.geometry?.type !== 'Polygon' ||
                !Array.isArray(point.forecasts) ||
                point.forecasts.length !== 49,
        )
    ) {
        throw new Error(
            'Incomplete corridor response. Submit the trip again to refresh its data.',
        )
    }

    return body as CorridorResponse
}