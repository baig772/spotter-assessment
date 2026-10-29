# Implementation assumptions

## Providers
- Mapbox Geocoding: resolve origin and destination.
- Mapbox Directions: driving routes with alternatives and segment timing.
- Open-Meteo: hourly wind, rain, showers, and snowfall.
- Mapbox GL JS: map rendering; browser integration remains to be tested.

## Routes and timing
- Request three routes; show fewer with an explanation when unavailable.
- Standard driving routes do not validate truck-specific road restrictions.
- Checkpoint ETA uses departure time plus cumulative segment duration.
- Rest breaks and weather-related speed adjustments are not modeled.
- Store and compare timestamps in UTC.

## Weather
- Wind: use wind_speed_10m in mph.
- Rain: (rain + showers) / 25.4 converts mm to inches.
- Snowfall: snowfall / 2.54 converts cm to inches.
- Hourly precipitation accumulations represent average rates over that hour.
- Match precipitation to its accumulation interval, not blindly to the
  nearest timestamp.
- Missing or out-of-range forecasts are unknown, never Low risk.

## Risk and recommendation
- Use the highest hazard severity, then apply the supplied load overrides.
- Shared rain/snow boundaries enter the higher band, except No Travel
  remains strictly above 1 inch/hour rain or 3 inches/hour snow.
- Segment risk is the higher risk of its bounding checkpoints.
- Average risk is distance-weighted: Low=0, Moderate=1, High=2, Severe=3.
- Exclude No Travel and incompletely assessed routes from recommendations.
- Rank eligible routes by Severe miles, High miles, average risk, then duration.

## Forecast map
- The slider covers hours 0–48 from a displayed forecast reference time.
- Slider weather is separate from arrival-time checkpoint weather.
- Use a bounded, uniform corridor grid and reuse loaded hourly forecasts.
- Heatmap intensity is illustrative; checkpoint values provide exact readings.

## Validation
- Chicago to Indianapolis returned two distinct routes.
- Both routes contained distance and duration annotations for every segment.
- Open-Meteo returned 72 hourly samples with the required weather fields.