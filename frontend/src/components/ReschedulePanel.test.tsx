import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Booking } from '../types';
import { ReschedulePanel } from './ReschedulePanel';

const now = Math.floor(Date.now() / 1000);
const slot = (id: number, start: number) => ({
  id,
  mentor_id: 2,
  starts_at: start,
  ends_at: start + 1800,
  enabled: true,
});
const booking = (extra: Partial<Booking> = {}) =>
  ({
    id: 'b1',
    status: 'confirmed',
    slot: slot(1, now + 86400),
    reschedule: null,
    group: null,
    ...extra,
  }) as Booking;

afterEach(cleanup);

describe('ReschedulePanel', () => {
  it('lets the other participant accept a proposal', async () => {
    const mutate = vi.fn().mockResolvedValue({});
    const proposal = {
      id: 7,
      proposed_slot: slot(2, now + 2 * 86400),
      requested_by: 1,
      expires_at: now + 3600,
    };
    render(
      <ReschedulePanel
        booking={booking({ reschedule: proposal })}
        userId={2}
        mutate={mutate}
        working={false}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Перенести' }));
    expect(mutate).toHaveBeenCalledWith('/reschedule/7/accept', {});
    expect(screen.queryByText('Отозвать предложение')).toBeNull();
  });

  it('lets the author withdraw their own proposal', async () => {
    const mutate = vi.fn().mockResolvedValue({});
    const proposal = {
      id: 7,
      proposed_slot: slot(2, now + 2 * 86400),
      requested_by: 1,
      expires_at: now + 3600,
    };
    render(
      <ReschedulePanel
        booking={booking({ reschedule: proposal })}
        userId={1}
        mutate={mutate}
        working={false}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Отозвать предложение' }));
    expect(mutate).toHaveBeenCalledWith('/reschedule/7/cancel', {});
  });

  it('offers no move for past or group lessons', () => {
    const { rerender } = render(
      <ReschedulePanel
        booking={booking({ slot: slot(1, now - 3600) })}
        userId={1}
        mutate={vi.fn()}
        working={false}
      />,
    );
    expect(screen.queryByText(/Предложить другое время/)).toBeNull();
    rerender(
      <ReschedulePanel
        booking={booking({ group: { capacity: 4, taken: 2, participants: [] } })}
        userId={1}
        mutate={vi.fn()}
        working={false}
      />,
    );
    expect(screen.queryByText(/Предложить другое время/)).toBeNull();
  });
});
