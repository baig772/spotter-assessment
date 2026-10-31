export interface TripRequest {
    origin: string
    destination: string
    departure_time: string
    sampling_interval_miles: number
    load_weight_lb: string
}

export type Coordinates = [number, number]

export type RiskLevel =
    | 'low'
    | 'moderate'
    | 'high'
    | 'severe'
    | 'no_travel'
    | 'unknown'

export interface Checkpoint {
    id: string
    coordinates: Coordinates
    distance_from_start_meters: number
    elapsed_seconds: number
    arrival_time: string
    weather: {
        status: 'available' | 'unknown'
        reason?: string
        wind_mph: number | null
        rain_inches_per_hour: number | null
        snow_inches_per_hour: number | null
    }
    risk: {
        severity: RiskLevel
        score: number | null
        reasons: string[]
    }
}

export interface RouteOption {
    id: string
    distance_meters: number
    duration_seconds: number
    recommended: boolean
    rank: number | null
    geometry: {
        type: 'LineString'
        coordinates: Coordinates[]
    }
    segments: {
        distances_meters: number[]
        durations_seconds: number[]
    }
    checkpoints: Checkpoint[]
    risk_summary: {
        eligible: boolean
        average_risk: number | null
        risk_miles: Record<RiskLevel, number>
        exclusion_reasons: string[]
        risk_segments: Array<{
            start_checkpoint_id: string
            end_checkpoint_id: string
            start_distance_meters: number
            end_distance_meters: number
            distance_meters: number
            severity: RiskLevel
        }>
    }
}

export interface RouteResponse {
    origin: {
        name: string
        coordinates: Coordinates
    }
    destination: {
        name: string
        coordinates: Coordinates
    }
    departure_time: string
    sampling_interval_miles: number
    load_weight_lb: string
    routes: RouteOption[]
    recommendation: {
        route_id: string | null
        eligible_route_ids: string[]
        reason: string
    }
    warnings: string[]
}

export class ApiError extends Error {
    fields: Record<string, string>

    constructor(message: string, fields: Record<string, string> = {}) {
        super(message)
        this.name = 'ApiError'
        this.fields = fields
    }
}

const baseUrl = (
    import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'
).replace(/\/+$/, '')

export async function planTrip(
    trip: TripRequest,
): Promise<RouteResponse> {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 120_000)

    try {
        const response = await fetch(`${baseUrl}/routes/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(trip),
            signal: controller.signal,
        })

        const body: unknown = await response.json().catch(() => null)

        if (!response.ok) {
            const fields: Record<string, string> = {}
            let message = `Request failed (${response.status}). Please try again.`

            if (body && typeof body === 'object') {
                for (const [key, value] of Object.entries(body)) {
                    const text = Array.isArray(value)
                        ? value.join(' ')
                        : typeof value === 'string'
                            ? value
                            : ''

                    if (!text) continue

                    if (key === 'detail' || key === 'non_field_errors') {
                        message = text
                    } else {
                        fields[key] = text
                    }
                }
            }

            if (Object.keys(fields).length) {
                message = 'Please correct the highlighted fields.'
            }

            throw new ApiError(message, fields)
        }

        if (
            !body ||
            typeof body !== 'object' ||
            !('routes' in body) ||
            !Array.isArray(body.routes) ||
            !('recommendation' in body) ||
            !body.recommendation
        ) {
            throw new ApiError('The server returned an unexpected response.')
        }

        return body as RouteResponse
    } catch (error) {
        if (error instanceof ApiError) {
            throw error
        }

        if (controller.signal.aborted) {
            throw new ApiError(
                'The request timed out. Please try again with a shorter trip.',
            )
        }

        throw new ApiError(
            'Could not connect to the server. Check your connection and try again.',
        )
    } finally {
        window.clearTimeout(timeout)
    }
}