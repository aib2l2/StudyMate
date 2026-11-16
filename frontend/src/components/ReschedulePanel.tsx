import { CalendarClock, Download } from 'lucide-react';
import { useState } from 'react';
import { api, clock, dateTime, download } from '../api';
import type { Booking, Mutate, Slot } from '../types';
import { ErrorText } from '../ui';

/** Propose / answer a move to another slot, and export the lesson to a calendar. */
export function ReschedulePanel({
  booking: b,
  userId,
  mutate,
  working,
}: {
  booking: Booking;
  userId: number;
  mutate: Mutate;
  working: boolean;
}) {
  const [options, setOptions] = useState<Slot[] | null>(null),
    [error, setError] = useState('');
  const movable =
    ['pending', 'confirmed'].includes(b.status) && b.slot.starts_at > clock() && !b.group;
  const run = async (action: () => Promise<unknown>) => {
    setError('');
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const req = b.reschedule;
  return (
    <div className="reschedule-panel">
      <span className="mono">ВРЕМЯ ВСТРЕЧИ</span>
      {req ? (
        <>
          <h3>Предложено новое время</h3>
          <p>
            {dateTime(req.proposed_slot.starts_at)}
            <br />
            <small className="muted">Ответить до {dateTime(req.expires_at)}</small>
          </p>
          {req.requested_by === userId ? (
            <button
              className="button full"
              disabled={working}
              onClick={() => void run(() => mutate(`/reschedule/${req.id}/cancel`, {}))}
            >
              Отозвать предложение
            </button>
          ) : (
            <div className="button-pair">
              <button
                className="button button-dark"
                disabled={working}
                onClick={() => void run(() => mutate(`/reschedule/${req.id}/accept`, {}))}
              >
                Перенести
              </button>
              <button
                className="button"
                disabled={working}
                onClick={() => void run(() => mutate(`/reschedule/${req.id}/decline`, {}))}
              >
                Оставить как есть
              </button>
            </div>
          )}
        </>
      ) : (
        movable && (
          <>
            {options === null ? (
              <button
                className="button full"
                onClick={() =>
                  void run(async () =>
                    setOptions(await api<Slot[]>(`/bookings/${b.id}/reschedule-options`)),
                  )
                }
              >
                Предложить другое время <CalendarClock size={16} />
              </button>
            ) : options.length ? (
              <fieldset className="reschedule-options">
                <legend>Свободное время ментора</legend>
                {options.map((slot) => (
                  <button
                    key={slot.id}
                    className="inline-link"
                    disabled={working}
                    onClick={() =>
                      void run(async () => {
                        await mutate(`/bookings/${b.id}/reschedule`, { slot_id: slot.id });
                        setOptions(null);
                      })
                    }
                  >
                    {dateTime(slot.starts_at)}
                  </button>
                ))}
              </fieldset>
            ) : (
              <p className="muted">У ментора пока нет другого свободного времени.</p>
            )}
            <p className="micro">
              Заметки, переписка и цена сохранятся. Перенос — по согласию обоих.
            </p>
          </>
        )
      )}
      {b.status === 'confirmed' && (
        <button
          className="inline-link"
          onClick={() =>
            void run(() => download(`/bookings/${b.id}/calendar.ics`, 'studymate-lesson.ics'))
          }
        >
          Добавить в календарь (.ics) <Download size={15} />
        </button>
      )}
      <ErrorText message={error} />
    </div>
  );
}
