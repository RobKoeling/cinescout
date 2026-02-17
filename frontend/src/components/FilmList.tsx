import FilmCard from './FilmCard'
import type { Cinema, FilmWithCinemas } from '../types'

interface FilmListProps {
  films: FilmWithCinemas[]
  onCinemaClick: (cinema: Cinema) => void
}

function FilmList({ films, onCinemaClick }: FilmListProps) {
  if (films.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">No films found for this time window</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {films.map((filmWithCinemas) => (
        <FilmCard
          key={filmWithCinemas.film.id}
          filmWithCinemas={filmWithCinemas}
          allFilms={films}
          onCinemaClick={onCinemaClick}
        />
      ))}
    </div>
  )
}

export default FilmList
