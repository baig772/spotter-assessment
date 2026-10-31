import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, planTrip } from './api/routes'
import type { RouteResponse } from './api/routes'
import RouteResults from './components/RouteResults'
import './App.css'

function initialDeparture() {
  const date = new Date(Date.now() + 60 * 60 * 1000)
  const pad = (value: number) => String(value).padStart(2, '0')

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

export default function App() {
  const [departure] = useState(initialDeparture)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [result, setResult] = useState<RouteResponse | null>(null)

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone

  function clearFeedback() {
    setError('')
    setFieldErrors({})
    setResult(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (loading) return

    const form = new FormData(event.currentTarget)
    const origin = String(form.get('origin') || '').trim()
    const destination = String(form.get('destination') || '').trim()
    const departureDate = new Date(String(form.get('departure_time')))
    const load = String(form.get('load_weight_lb') || '').trim()

    clearFeedback()

    const errors: Record<string, string> = {}

    if (!origin) errors.origin = 'Enter an origin.'
    if (!destination) errors.destination = 'Enter a destination.'

    if (origin && origin.toLowerCase() === destination.toLowerCase()) {
      errors.destination = 'Choose a different destination.'
    }

    if (
      Number.isNaN(departureDate.getTime()) ||
      departureDate.getTime() <= Date.now()
    ) {
      errors.departure_time = 'Choose a future departure time.'
    }

    if (!load || !Number.isFinite(Number(load)) || Number(load) < 0) {
      errors.load_weight_lb = 'Enter a load weight of zero or more.'
    }

    if (Object.keys(errors).length) {
      setFieldErrors(errors)
      setError('Please correct the highlighted fields.')
      return
    }

    setLoading(true)

    try {
      const response = await planTrip({
        origin,
        destination,
        departure_time: departureDate.toISOString(),
        load_weight_lb: load,
        sampling_interval_miles: Number(
          form.get('sampling_interval_miles'),
        ),
      })

      setResult(response)
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message)
        setFieldErrors(caught.fields)
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  function fieldError(name: string) {
    return fieldErrors[name] ? (
      <span className="field-error" id={`${name}-error`}>
        {fieldErrors[name]}
      </span>
    ) : null
  }

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">SPOTTER · ROUTE PLANNER</p>
        <h1>Know the weather ahead.</h1>
        <p>Compare driving routes using arrival-time forecasts and load weight.</p>
      </header>

      <div className="planner-layout">
        <section className="panel" aria-labelledby="trip-heading">
          <h2 id="trip-heading">Plan your trip</h2>

          <form onSubmit={handleSubmit} onChange={clearFeedback}>
            <fieldset disabled={loading}>
              {[
                ['origin', 'Origin', 'Chicago, Illinois'],
                ['destination', 'Destination', 'Indianapolis, Indiana'],
              ].map(([name, label, placeholder]) => (
                <label key={name}>
                  {label}
                  <input
                    name={name}
                    placeholder={placeholder}
                    maxLength={250}
                    required
                    aria-invalid={Boolean(fieldErrors[name])}
                    aria-describedby={
                      fieldErrors[name] ? `${name}-error` : undefined
                    }
                  />
                  {fieldError(name)}
                </label>
              ))}

              <label>
                Departure date and time
                <input
                  name="departure_time"
                  type="datetime-local"
                  defaultValue={departure}
                  required
                  aria-invalid={Boolean(fieldErrors.departure_time)}
                  aria-describedby="departure-help departure_time-error"
                />
                <span className="help" id="departure-help">
                  Time zone: {timezone}. Converted to UTC when submitted.
                </span>
                <span id="departure_time-error" className="field-error">
                  {fieldErrors.departure_time}
                </span>
              </label>

              <label>
                Load weight (lb)
                <input
                  name="load_weight_lb"
                  type="number"
                  min="0"
                  max="99999999.99"
                  step="0.01"
                  placeholder="45000"
                  required
                  aria-invalid={Boolean(fieldErrors.load_weight_lb)}
                  aria-describedby={
                    fieldErrors.load_weight_lb
                      ? 'load_weight_lb-error'
                      : undefined
                  }
                />
                {fieldError('load_weight_lb')}
              </label>

              <label>
                Weather checkpoint spacing
                <select
                  name="sampling_interval_miles"
                  defaultValue="25"
                  aria-invalid={Boolean(fieldErrors.sampling_interval_miles)}
                  aria-describedby={
                    fieldErrors.sampling_interval_miles
                      ? 'sampling_interval_miles-error'
                      : undefined
                  }
                >
                  <option value="10">Every 10 miles</option>
                  <option value="25">Every 25 miles</option>
                  <option value="50">Every 50 miles</option>
                </select>
                {fieldError('sampling_interval_miles')}
              </label>

              <button type="submit">
                {loading ? 'Checking routes and weather…' : 'Compare routes'}
              </button>
            </fieldset>

            {error && <p className="error-message" role="alert">{error}</p>}
          </form>
        </section>

        <section
          className="panel results-panel"
          aria-labelledby="results-heading"
          aria-busy={loading}
        >
          <h2 id="results-heading">Trip overview</h2>

          <div role="status">
            {loading && <p>Finding routes and checking checkpoint forecasts…</p>}

            {!loading && !result && (
              <p className="muted">
                Enter your trip details to compare available routes.
              </p>
            )}

            {result && (
              <>
                <h3>{result.origin.name} → {result.destination.name}</h3>
                <p>{result.routes.length} route options returned.</p>
                {result.warnings.map((warning, index) => (
                  <p className="notice" key={index}>{warning}</p>
                ))}
                <p>
                  <strong>
                    {result.recommendation.route_id
                      ? `Recommended: ${result.recommendation.route_id}`
                      : 'No route recommended'}
                  </strong>
                </p>
                <p>{result.recommendation.reason}</p>
                <RouteResults
                  key={result.route_plan_id}
                  routes={result.routes}
                  planId={result.route_plan_id}
                />
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  )
}