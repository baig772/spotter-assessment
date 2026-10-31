from .checkpoints import METERS_PER_MILE
from .risk import SEVERITY_SCORES


RISK_LEVELS = (*SEVERITY_SCORES.keys(), "unknown")


def summarize_route(route):
    checkpoints = route["checkpoints"]
    risk_meters = {level: 0.0 for level in RISK_LEVELS}
    risk_segments = []

    if len(checkpoints) < 2:
        raise ValueError("A route needs at least two checkpoints.")

    checkpoint_levels = [
        point["risk"]["severity"] for point in checkpoints
    ]

    if any(level not in RISK_LEVELS for level in checkpoint_levels):
        raise ValueError("Unrecognized risk severity.")

    for start, end in zip(checkpoints, checkpoints[1:]):
        distance = (
            end["distance_from_start_meters"]
            - start["distance_from_start_meters"]
        )

        if distance <= 0:
            raise ValueError("Checkpoint distances must increase.")

        levels = (
            start["risk"]["severity"],
            end["risk"]["severity"],
        )

        if "no_travel" in levels:
            severity = "no_travel"
        elif "unknown" in levels:
            severity = "unknown"
        else:
            severity = max(levels, key=SEVERITY_SCORES.get)

        risk_meters[severity] += distance

        risk_segments.append({
            "start_checkpoint_id": start["id"],
            "end_checkpoint_id": end["id"],
            "start_distance_meters": start["distance_from_start_meters"],
            "end_distance_meters": end["distance_from_start_meters"],
            "distance_meters": distance,
            "severity": severity,
        })

    total_distance = sum(risk_meters.values())
    has_unknown = "unknown" in checkpoint_levels
    has_no_travel = "no_travel" in checkpoint_levels

    exclusion_reasons = []

    if has_no_travel:
        exclusion_reasons.append("Route contains No Travel conditions.")

    if has_unknown:
        exclusion_reasons.append("Route has incomplete weather assessment.")

    average_risk = None

    if not has_unknown:
        average_risk = sum(
            risk_meters[level] * score
            for level, score in SEVERITY_SCORES.items()
        ) / total_distance

    return {
        "assessed_distance_meters": total_distance,
        "risk_miles": {
            level: meters / METERS_PER_MILE
            for level, meters in risk_meters.items()
        },
        "average_risk": average_risk,
        "eligible": not exclusion_reasons,
        "exclusion_reasons": exclusion_reasons,
        "risk_segments": risk_segments,
    }


def ranking_key(route):
    summary = route["risk_summary"]

    return (
        summary["risk_miles"]["severe"],
        summary["risk_miles"]["high"],
        summary["average_risk"],
        route["duration_seconds"],
    )


def analyze_and_recommend(routes):
    for route in routes:
        route["risk_summary"] = summarize_route(route)
        route["recommended"] = False
        route["rank"] = None

    eligible = sorted(
        (
            route
            for route in routes
            if route["risk_summary"]["eligible"]
        ),
        key=ranking_key,
    )

    for rank, route in enumerate(eligible, start=1):
        route["rank"] = rank

    if not eligible:
        return {
            "route_id": None,
            "eligible_route_ids": [],
            "reason": (
                "No route can be recommended: every route has "
                "No Travel conditions or incomplete weather."
            ),
        }

    best = eligible[0]
    best["recommended"] = True

    if len(eligible) == 1:
        reason = (
            "The only fully assessed route without No Travel conditions."
        )
    else:
        runner_up = eligible[1]
        best_key = ranking_key(best)
        runner_up_key = ranking_key(runner_up)

        criteria = (
            "fewer Severe miles",
            "fewer High miles",
            "a lower distance-weighted average risk",
            "a shorter travel time",
        )

        reason = (
            "All ranking criteria are tied; selected the first "
            "route in provider order."
        )

        for index, criterion in enumerate(criteria):
            if best_key[index] < runner_up_key[index]:
                reason = (
                    f"Ranks first among eligible routes. Compared with "
                    f"{runner_up['id']}, it has {criterion}; "
                    "all higher-priority criteria are tied."
                )
                break

    return {
        "route_id": best["id"],
        "eligible_route_ids": [route["id"] for route in eligible],
        "reason": reason,
    }