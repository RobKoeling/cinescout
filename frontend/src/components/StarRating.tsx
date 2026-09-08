interface StarRatingProps {
  value: number | null
  onChange?: (value: number) => void
  readOnly?: boolean
}

const STARS = [1, 2, 3, 4, 5]

function StarRating({ value, onChange, readOnly = false }: StarRatingProps) {
  const displayValue = value ?? 0

  const handleClick = (star: number, half: boolean) => {
    if (readOnly || !onChange) return
    onChange(half ? star - 0.5 : star)
  }

  return (
    <div className="flex items-center gap-0.5" role={readOnly ? undefined : 'group'} aria-label="Rating">
      {STARS.map((star) => {
        const fillFraction = Math.max(0, Math.min(1, displayValue - (star - 1)))
        return (
          <span key={star} className="relative inline-block w-5 h-5 text-lg leading-none">
            <span className="absolute inset-0 text-gray-300 select-none">★</span>
            <span
              className="absolute inset-0 text-yellow-500 overflow-hidden select-none"
              style={{ width: `${fillFraction * 100}%` }}
            >
              ★
            </span>
            {!readOnly && (
              <>
                <button
                  type="button"
                  aria-label={`Rate ${star - 0.5} stars`}
                  className="absolute inset-y-0 left-0 w-1/2"
                  onClick={() => handleClick(star, true)}
                />
                <button
                  type="button"
                  aria-label={`Rate ${star} stars`}
                  className="absolute inset-y-0 right-0 w-1/2"
                  onClick={() => handleClick(star, false)}
                />
              </>
            )}
          </span>
        )
      })}
    </div>
  )
}

export default StarRating
