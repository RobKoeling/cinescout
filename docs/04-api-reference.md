# CineScout: API Reference

Base URL: `http://localhost:8000/api` (development)

## Authentication

No authentication required for MVP. Future versions will support user accounts.

## Endpoints

### Search Showings

Search for film showings within a date and time window.

```
GET /showings
```

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `date` | date | Yes | - | Date to search (YYYY-MM-DD) |
| `city` | string | No | `london` | City to search in |
| `time_from` | time | No | `00:00` | Earliest start time (HH:MM) |
| `time_to` | time | No | `23:59` | Latest start time (HH:MM) |

**Example Request:**

```bash
curl "http://localhost:8000/api/showings?date=2024-01-25&time_from=18:00&time_to=21:00"
```

**Success Response (200):**

```json
{
  "films": [
    {
      "film": {
        "id": "abc123",
        "title": "The Godfather",
        "year": 1972,
        "directors": ["Francis Ford Coppola"],
        "countries": ["US"],
        "showing_count": 2
      },
      "cinemas": [
        {
          "cinema": {
            "id": "prince-charles",
            "name": "Prince Charles Cinema",
            "slug": "prince-charles",
            "address": "7 Leicester Place, London WC2H 7BY",
            "city": "london",
            "website": "https://princecharlescinema.com",
            "supports_online_booking": true,
            "coordinates": {
              "lat": 51.5112,
              "lng": -0.1305
            },
            "contact": {
              "phone": "020 7494 3654",
              "email": null
            }
          },
          "times": [
            {
              "id": "showing-001",
              "start_time": "2024-01-25T18:30:00",
              "end_time": "2024-01-25T21:25:00",
              "screen": "Screen 1",
              "format": "35mm",
              "booking_url": "https://princecharlescinema.com/book/001",
              "price": {
                "amount": 12.50,
                "currency": "GBP"
              },
              "availability": "unknown"
            },
            {
              "id": "showing-002",
              "start_time": "2024-01-25T20:00:00",
              "end_time": null,
              "screen": "Screen 2",
              "format": "Digital",
              "booking_url": "https://princecharlescinema.com/book/002",
              "price": null,
              "availability": "unknown"
            }
          ]
        }
      ]
    }
  ],
  "total_films": 15,
  "total_showings": 42,
  "query": {
    "city": "london",
    "date": "2024-01-25",
    "time_from": "18:00",
    "time_to": "21:00"
  }
}
```

**Error Response (422):**

```json
{
  "detail": [
    {
      "loc": ["query", "date"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

### Check Availability

Check real-time ticket availability for a specific showing.

```
GET /showings/{showing_id}/availability
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `showing_id` | string | ID of the showing |

**Example Request:**

```bash
curl "http://localhost:8000/api/showings/showing-001/availability"
```

**Success Response (200):**

```json
{
  "showing_id": "showing-001",
  "availability": "available",
  "price": {
    "amount": 12.50,
    "currency": "GBP"
  },
  "message": null
}
```

**Availability Values:**

| Value | Description |
|-------|-------------|
| `available` | Tickets available for purchase |
| `limited` | Few tickets remaining |
| `sold_out` | No tickets available |
| `unknown` | Unable to determine availability |

**When availability cannot be checked:**

```json
{
  "showing_id": "showing-001",
  "availability": "unknown",
  "price": null,
  "message": "Availability check not supported for this cinema"
}
```

**Error Response (404):**

```json
{
  "detail": "Showing not found"
}
```

---

### List Cinemas

Get all active cinemas.

```
GET /cinemas
```

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `city` | string | No | - | Filter by city |

**Example Request:**

```bash
curl "http://localhost:8000/api/cinemas?city=london"
```

**Success Response (200):**

```json
{
  "cinemas": [
    {
      "id": "bfi-southbank",
      "name": "BFI Southbank",
      "slug": "bfi-southbank",
      "address": "Belvedere Road, South Bank, London SE1 8XT",
      "city": "london",
      "website": "https://www.bfi.org.uk/bfi-southbank",
      "supports_online_booking": true,
      "coordinates": {
        "lat": 51.5063,
        "lng": -0.1155
      },
      "contact": {
        "phone": "020 7928 3232",
        "email": "info@bfi.org.uk"
      }
    },
    {
      "id": "prince-charles",
      "name": "Prince Charles Cinema",
      "slug": "prince-charles",
      "address": "7 Leicester Place, London WC2H 7BY",
      "city": "london",
      "website": "https://princecharlescinema.com",
      "supports_online_booking": true,
      "coordinates": {
        "lat": 51.5112,
        "lng": -0.1305
      },
      "contact": {
        "phone": "020 7494 3654",
        "email": null
      }
    }
  ],
  "count": 2
}
```

---

### Get Film Details

Get detailed information about a specific film.

```
GET /films/{film_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `film_id` | string | ID of the film |

**Example Request:**

```bash
curl "http://localhost:8000/api/films/abc123"
```

**Success Response (200):**

```json
{
  "id": "abc123",
  "title": "The Godfather",
  "original_title": "The Godfather",
  "year": 1972,
  "directors": ["Francis Ford Coppola"],
  "countries": ["US"],
  "runtime_minutes": 175,
  "poster_url": "https://image.tmdb.org/t/p/w500/3bhkrj58Vtu7enYsRolD1fZdja1.jpg",
  "synopsis": "Spanning the years 1945 to 1955, a chronicle of the fictional Italian-American Corleone crime family...",
  "tmdb_id": 238,
  "imdb_id": "tt0068646"
}
```

**Error Response (404):**

```json
{
  "detail": "Film not found"
}
```

---

### Admin: Trigger Scrape

Manually trigger a scrape for specific cinemas (development only).

```
POST /admin/scrape
```

**Request Body:**

```json
{
  "cinema_ids": ["bfi-southbank", "prince-charles"],
  "date_from": "2024-01-25",
  "date_to": "2024-01-26"
}
```

**Success Response (202):**

```json
{
  "status": "accepted",
  "message": "Scrape job queued",
  "job_id": "job-12345"
}
```

---

## Data Types

### Film

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `title` | string | Film title |
| `original_title` | string? | Original language title |
| `year` | int? | Release year |
| `directors` | string[] | List of director names |
| `countries` | string[] | ISO country codes |
| `runtime_minutes` | int? | Runtime in minutes |
| `poster_url` | string? | URL to poster image |
| `synopsis` | string? | Film description |
| `tmdb_id` | int? | TMDb identifier |
| `imdb_id` | string? | IMDb identifier |

### Cinema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `name` | string | Cinema name |
| `slug` | string | URL-friendly name |
| `address` | string | Full address |
| `city` | string | City name |
| `website` | string | Cinema website URL |
| `supports_online_booking` | bool | Whether online booking is available |
| `coordinates` | Coordinates? | Lat/lng for maps |
| `contact` | ContactDetails? | Phone/email |

### ShowingTime

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `start_time` | datetime | ISO 8601 start time |
| `end_time` | datetime? | ISO 8601 end time |
| `screen` | string? | Screen/auditorium name |
| `format` | string? | Screening format (35mm, IMAX, etc.) |
| `booking_url` | string? | Direct booking link |
| `price` | Price? | Ticket price |
| `availability` | AvailabilityStatus | Ticket availability |

### AvailabilityStatus

Enum: `available`, `limited`, `sold_out`, `unknown`

### Price

| Field | Type | Description |
|-------|------|-------------|
| `amount` | float | Price value |
| `currency` | string | ISO currency code (default: GBP) |

### Coordinates

| Field | Type | Description |
|-------|------|-------------|
| `lat` | float | Latitude |
| `lng` | float | Longitude |

### ContactDetails

| Field | Type | Description |
|-------|------|-------------|
| `phone` | string? | Phone number |
| `email` | string? | Email address |

---

## Error Handling

All errors follow this format:

```json
{
  "detail": "Error message"
}
```

Or for validation errors:

```json
{
  "detail": [
    {
      "loc": ["query", "field_name"],
      "msg": "error description",
      "type": "error_type"
    }
  ]
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 202 | Accepted (async operation started) |
| 400 | Bad request (invalid parameters) |
| 404 | Resource not found |
| 422 | Validation error |
| 500 | Internal server error |

---

## Rate Limiting

No rate limiting in MVP. Future versions may implement limits.

---

## OpenAPI Documentation

When the backend is running, interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
