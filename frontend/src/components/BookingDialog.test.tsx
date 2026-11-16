import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { defaultFilters } from '../api';
import type { Mentor } from '../types';
import { BookingDialog } from './BookingDialog';

const mentor = {
  id: 2,
  name: 'Аяулым',
  price: 2500,
  slots: [
    { id: 10, mentor_id: 2, starts_at: 2e9, ends_at: 2e9 + 1800, enabled: true, capacity: 1 },
    {
      id: 11,
      mentor_id: 2,
      starts_at: 2e9 + 3600,
      ends_at: 2e9 + 5400,
      enabled: true,
      capacity: 4,
      taken: 1,
      price: 1200,
      topic_id: 2,
      format: 'campus',
    },
  ],
} as unknown as Mentor;
const filters = { ...defaultFilters([]), topic_id: 1, format: 'online' };

beforeAll(() => {
  // jsdom has no <dialog> modal API.
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.open = false;
  };
});
afterEach(cleanup);

async function book(slotId: number) {
  const submit = vi.fn().mockResolvedValue(undefined);
  render(
    <BookingDialog
      mentor={mentor}
      slotId={slotId}
      topicId={1}
      filters={filters}
      close={vi.fn()}
      working={false}
      submit={submit}
    />,
  );
  await userEvent.type(screen.getByRole('textbox'), 'Хочу разобраться');
  await userEvent.click(
    screen.getByRole('button', { name: /Отправить заявку|Записаться в группу/ }),
  );
  return submit.mock.calls[0][0];
}

describe('BookingDialog', () => {
  it('keeps the chosen topic and format for a 1:1 lesson', async () => {
    const body = await book(10);
    expect(body).toMatchObject({ slot_id: 10, topic_id: 1, format: 'online' });
    expect(screen.getByText('2 500 ₸')).toBeTruthy();
  });

  it('uses the group topic, format and seat price', async () => {
    const body = await book(11);
    expect(body).toMatchObject({ slot_id: 11, topic_id: 2, format: 'campus' });
    expect(screen.getByText(/занято 1 из 4/)).toBeTruthy();
  });
});
