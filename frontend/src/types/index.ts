// TypeScript types matching the backend API schemas

export interface Film {
  id: string
  title: string
  year: number | null
  directors: string[] | null
  countries: string[] | null
  cast: string[] | null
  runtime: number | null
  overview: string | null
  poster_path: string | null
  tmdb_id: number | null
}

export interface FilmWithShowingCount extends Film {
  showing_count: number
}

export interface Cinema {
  id: string
  name: string
  city: string
  address: string
  postcode: string
  latitude: number | null
  longitude: number | null
  website: string | null
  has_online_booking: boolean
  supports_availability_check: boolean
  // Distance/travel time fields (populated when user location provided)
  distance_km?: number
  distance_miles?: number
  travel_time_minutes?: number
  travel_mode?: 'public'
}

export interface ShowingTime {
  id: number
  start_time: string
  screen_name: string | null
  format_tags: string | null
  booking_url: string | null
  price: number | null
  estimated_price: number | null
  raw_title: string | null
}

export interface CinemaWithShowings {
  cinema: Cinema
  times: ShowingTime[]
}

export interface FilmWithCinemas {
  film: FilmWithShowingCount
  cinemas: CinemaWithShowings[]
}

export interface ShowingsQuery {
  date: string
  city: string
  time_from: string
  time_to: string
}

export interface ShowingsResponse {
  films: FilmWithCinemas[]
  total_films: number
  total_showings: number
  query: ShowingsQuery
}

export interface UserLocation {
  lat: number
  lng: number
}

export interface SearchParams {
  date: string
  city: string
  timeFrom: string
  timeTo: string
  userLocation?: UserLocation
  useTfL?: boolean
  transportMode?: 'public'
}
