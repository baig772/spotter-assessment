import type { FeatureCollection, LineString, Point } from 'geojson'
import type { RiskLevel, RouteOption } from '../api/routes'

export const riskColors: Record<RiskLevel, string> = {
    low: '#16805d',
    moderate: '#b88700',
    high: '#e36c16',
    severe: '#d43131',
    no_travel: '#781f58',
    unknown: '#667788',
}

export function createMapData(routes: RouteOption[]) {
    const lines: FeatureCollection<LineString> = {
        type: 'FeatureCollection',
        features: [],
    }

    const risks: FeatureCollection<LineString> = {
        type: 'FeatureCollection',
        features: [],
    }

    const points: FeatureCollection<Point> = {
        type: 'FeatureCollection',
        features: [],
    }

    for (const route of routes) {
        lines.features.push({
            type: 'Feature',
            properties: { routeId: route.id },
            geometry: route.geometry,
        })

        const cumulative = [0]

        for (const distance of route.segments.distances_meters) {
            cumulative.push(cumulative[cumulative.length - 1] + distance)
        }

        const checkpoints = new Map(
            route.checkpoints.map((checkpoint) => [checkpoint.id, checkpoint]),
        )

        for (const segment of route.risk_summary.risk_segments) {
            const start = checkpoints.get(segment.start_checkpoint_id)
            const end = checkpoints.get(segment.end_checkpoint_id)

            if (!start || !end) {
                throw new Error('Risk segment references a missing checkpoint.')
            }

            // Preserve every road vertex inside this checkpoint interval.
            const interior = route.geometry.coordinates.filter(
                (_, index) =>
                    cumulative[index] > segment.start_distance_meters &&
                    cumulative[index] < segment.end_distance_meters,
            )

            risks.features.push({
                type: 'Feature',
                properties: {
                    routeId: route.id,
                    color: riskColors[segment.severity],
                },
                geometry: {
                    type: 'LineString',
                    coordinates: [start.coordinates, ...interior, end.coordinates],
                },
            })
        }

        for (const checkpoint of route.checkpoints) {
            points.features.push({
                type: 'Feature',
                properties: {
                    routeId: route.id,
                    checkpointId: checkpoint.id,
                    color: riskColors[checkpoint.risk.severity],
                },
                geometry: {
                    type: 'Point',
                    coordinates: checkpoint.coordinates,
                },
            })
        }
    }

    return { lines, risks, points }
}