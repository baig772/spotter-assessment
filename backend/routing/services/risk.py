from math import isfinite


SEVERITY_SCORES = {
    "low": 0,
    "moderate": 1,
    "high": 2,
    "severe": 3,
    "no_travel": 4,
}


def classify_wind(value):
    if value >= 55:
        return "no_travel"
    if value >= 45:
        return "severe"
    if value >= 35:
        return "high"
    if value >= 25:
        return "moderate"
    return "low"


def classify_rain(value):
    if value > 1.00:
        return "no_travel"
    if value >= 0.50:
        return "severe"
    if value >= 0.25:
        return "high"
    if value >= 0.10:
        return "moderate"
    return "low"


def classify_snow(value):
    if value > 3.0:
        return "no_travel"
    if value >= 2.0:
        return "severe"
    if value >= 1.0:
        return "high"
    if value >= 0.5:
        return "moderate"
    return "low"


def unknown_risk(reason):
    return {
        "severity": "unknown",
        "score": None,
        "hazards": {},
        "load_override": None,
        "reasons": [reason],
    }


def assess_checkpoint_risk(weather, load_weight_lb):
    if weather.get("status") != "available":
        return unknown_risk(
            weather.get("reason") or "Weather is unavailable."
        )

    wind = weather.get("wind_mph")
    rain = weather.get("rain_inches_per_hour")
    snow = weather.get("snow_inches_per_hour")

    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not isfinite(value)
        or value < 0
        for value in (wind, rain, snow)
    ):
        return unknown_risk("Required weather readings are invalid.")

    hazards = {
        "wind": classify_wind(wind),
        "rain": classify_rain(rain),
        "snow": classify_snow(snow),
    }

    severity = max(hazards.values(), key=SEVERITY_SCORES.get)

    readings = {
        "wind": f"{wind:g} mph",
        "rain": f"{rain:g} in/hr",
        "snow": f"{snow:g} in/hr",
    }

    reasons = [
        f"{hazard.title()} {readings[hazard]}: "
        f"{level.replace('_', ' ').title()}."
        for hazard, level in hazards.items()
        if level != "low"
    ]

    load_override = None

    if 45 <= wind < 55 and load_weight_lb > 30000:
        load_override = "no_travel"
        reasons.append(
            "Wind is at least 45 but below 55 mph and load exceeds "
            "30,000 lb: No Travel."
        )
    elif 35 <= wind < 45 and load_weight_lb > 40000:
        load_override = "severe"
        reasons.append(
            "Wind is at least 35 but below 45 mph and load exceeds "
            "40,000 lb: Severe."
        )

    # An override must never reduce a higher rain or snow severity.
    if load_override is not None:
        severity = max(
            (severity, load_override),
            key=SEVERITY_SCORES.get,
        )

    if not reasons:
        reasons.append(
            "Wind, rain, and snow are below the Moderate thresholds."
        )

    return {
        "severity": severity,
        "score": SEVERITY_SCORES[severity],
        "hazards": hazards,
        "load_override": load_override,
        "reasons": reasons,
    }


def attach_checkpoint_risks(routes, load_weight_lb):
    for route in routes:
        for checkpoint in route["checkpoints"]:
            checkpoint["risk"] = assess_checkpoint_risk(
                checkpoint["weather"],
                load_weight_lb,
            )