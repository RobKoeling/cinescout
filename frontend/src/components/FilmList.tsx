import FilmCard from './FilmCard'
import type { FilmWithCinemas } from '../types'

interface FilmListProps {
  films: FilmWithCinemas[]
}

function FilmList({ films }: FilmListProps) {
  if (films.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">No films found for this time window</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {films.map((filmWithCinemas) => (
        <FilmCard key={filmWithCinemas.film.id} filmWithCinemas={filmWithCinemas} />
      ))}
    </div>
  )
}

export default FilmList
