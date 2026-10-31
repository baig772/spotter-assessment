# Spotter — Weather-Aware Route Planner

A React and Django application that compares driving routes using forecast
weather at estimated checkpoint arrival times and load-dependent risk rules.

## Live application

- Frontend: https://spotter-assessment-1.onrender.com/
- Backend health: https://spotter-assessment-7mv9.onrender.com/api/health/
- Repository: https://github.com/baig772/spotter-assessment

## Features

- Origin, destination, departure time, and load-weight inputs.
- Up to three alternative routes from Mapbox.
- Weather checkpoints spaced every 10, 25, or 50 miles.
- Checkpoint arrival times calculated using route segment durations.
- Wind, rain, and snow risk classification with load-dependent overrides.
- Route comparison, ranking, and an explained recommendation.
- Interactive routes and checkpoint details on a Mapbox map.
- Corridor weather overlay with hourly forecasts from +0 to +48 hours.
- Explicit handling of unavailable forecasts and ineligible routes.

## Technology

- React, TypeScript, Vite, and Mapbox GL JS
- Python, Django, and Django REST Framework
- Mapbox geocoding and directions
- Open-Meteo weather forecasts
- Render hosting

## Local setup

### Backend

Requires Python 3.13.

```bash
git clone https://github.com/baig772/spotter-assessment.git
cd spotter-assessment/backend

python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` with the environment-variable names used by
`config/settings.py`:

```dotenv
SECRET_KEY=replace-with-a-local-development-secret
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
MAPBOX_ACCESS_TOKEN=your-mapbox-token
```

Then run:

```bash
python manage.py migrate
python manage.py runserver
```

### Frontend

Requires Node.js 22 and pnpm.

```bash
cd frontend
pnpm install --frozen-lockfile
```

Create `frontend/.env.local`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api
VITE_MAPBOX_ACCESS_TOKEN=your-public-mapbox-token
```

Start the frontend:

```bash
pnpm dev
```

Keep secrets and local environment files out of version control.
The frontend Mapbox token is public; configure appropriate URL restrictions.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health/` | GET | Service health |
| `/api/routes/` | POST | Routes, checkpoints, weather, and recommendation |
| `/api/corridor-weather/` | POST | Hourly corridor weather for a cached route plan |

Example route request:

```json
{
  "origin": "Chicago, Illinois",
  "destination": "Indianapolis, Indiana",
  "departure_time": "<future ISO 8601 datetime with timezone>",
  "load_weight_lb": "45000",
  "sampling_interval_miles": 25
}
```

Use the returned `route_plan_id` for corridor weather:

```json
{
  "route_plan_id": "<returned route plan ID>"
}
```

## Processing flow

1. Validate inputs and geocode the locations.
2. Request alternative driving routes.
3. Sample checkpoints along each route.
4. Calculate checkpoint arrival times from segment timing.
5. Retrieve weather for each checkpoint's location and arrival time.
6. Classify risk and apply load-dependent rules.
7. Aggregate risk by distance and rank eligible routes.
8. Generate corridor weather separately for the map timeline.

## Risk and recommendation

Weather severity uses the assessment's wind, rain, and snow thresholds.
The most severe applicable hazard determines checkpoint risk.

Load-dependent wind rules:

- Wind at least 55 mph: No Travel for any load.
- Wind from 45 to below 55 mph with load above 30,000 lb: No Travel.
- Wind from 35 to below 45 mph with load above 40,000 lb: Severe.

Routes containing No Travel conditions or unavailable checkpoint weather
are excluded from recommendations.

Eligible routes are ranked in this order:

1. Fewest Severe miles.
2. Fewest High miles.
3. Lowest distance-weighted average risk.
4. Shortest travel time.

Risk scores are Low = 0, Moderate = 1, High = 2, Severe = 3,
and No Travel = 4. Unknown weather is not treated as Low.

## Assumptions and limitations

- Mapbox may return fewer than three distinct routes. The application
  displays the available alternatives and a warning.
- Routes use Mapbox's driving profile and do not guarantee compliance
  with truck height, weight, or hazardous-material restrictions.
- Travel times do not include rest breaks or loading stops.
- Checkpoint positions and times are interpolated within route segments.
- Risk between checkpoints uses the worse endpoint classification.
- Departure input and displayed times use the browser's timezone.
  Backend calculations use UTC.
- Weather outside the returned forecast window remains Unknown.
- Corridor forecasts start at the current UTC hour and cover 48 hours.
  They are separate from the arrival-time weather used to rank routes.
- Corridor grid spacing increases for larger trips to limit API usage.
- Route plans use process-local caching and expire after one hour.
  Restarting the backend invalidates cached plans.
- The current deployment uses one backend worker. Multiple workers or
  instances would require shared caching.
- The interactive map requires WebGL. A map error boundary preserves
  the route comparison if map initialization fails.

## Verification

Backend:

```bash
cd backend
source .venv/bin/activate
python manage.py test routing
```

Frontend:

```bash
cd frontend
pnpm lint
pnpm build
```

Automated coverage includes checkpoint timing, weather handling,
risk classification, recommendations, and corridor behavior.

Manual deployment checks include route searches, checkpoint spacing,
route selection, checkpoint inspection, heatmap controls, forecast
availability, validation, and responsive layout.

## Deployment

The frontend is deployed as a Render static site.
The Django backend runs on Render using Gunicorn and WhiteNoise.

Frontend build:

```bash
pnpm install --frozen-lockfile && pnpm build
```

Publish directory: `dist`

Backend start:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180 --access-logfile - --error-logfile -
```

Production configuration includes `DEBUG=False`, the deployed frontend
origin in CORS settings, and the backend hostname in allowed hosts.
