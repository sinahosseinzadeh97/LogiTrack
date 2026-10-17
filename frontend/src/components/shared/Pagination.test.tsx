import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Pagination } from './Pagination'

describe('Pagination', () => {
  it('shows the position and disables the edges', () => {
    const onChange = vi.fn()
    render(<Pagination page={1} pageSize={25} total={60} noun="orders" onChange={onChange} />)

    expect(screen.getByText('Page 1 of 3 · 60 orders')).toBeTruthy()
    expect((screen.getByText('Prev') as HTMLButtonElement).disabled).toBe(true)

    fireEvent.click(screen.getByText('Next'))
    expect(onChange).toHaveBeenCalledWith(2)
  })

  it('treats an empty result as a single page', () => {
    render(<Pagination page={1} pageSize={25} total={0} noun="orders" onChange={() => undefined} />)
    expect((screen.getByText('Next') as HTMLButtonElement).disabled).toBe(true)
  })
})
