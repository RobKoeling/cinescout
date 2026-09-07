import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import StarRating from './StarRating'

describe('StarRating', () => {
  it('renders no clickable buttons in read-only mode', () => {
    render(<StarRating value={3.5} readOnly />)
    expect(screen.queryAllByRole('button')).toHaveLength(0)
  })

  it('renders click targets for each half-star in interactive mode', () => {
    render(<StarRating value={null} onChange={vi.fn()} />)
    // 5 stars x 2 half-star click targets each
    expect(screen.getAllByRole('button')).toHaveLength(10)
  })

  it('calls onChange with a whole number when the right half of a star is clicked', () => {
    const onChange = vi.fn()
    render(<StarRating value={null} onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Rate 3 stars'))
    expect(onChange).toHaveBeenCalledWith(3)
  })

  it('calls onChange with a half value when the left half of a star is clicked', () => {
    const onChange = vi.fn()
    render(<StarRating value={null} onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Rate 2.5 stars'))
    expect(onChange).toHaveBeenCalledWith(2.5)
  })

  it('does not call onChange when readOnly', () => {
    const onChange = vi.fn()
    render(<StarRating value={3} onChange={onChange} readOnly />)
    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(onChange).not.toHaveBeenCalled()
  })
})
