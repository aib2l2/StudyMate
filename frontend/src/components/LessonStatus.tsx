import { ArrowUpRight } from 'lucide-react';
import { shortTime } from '../api';
import type { Booking, Navigate } from '../types';
import { Badge } from '../ui';

export const active = (b: Booking) => ['pending', 'confirmed'].includes(b.status);
export function Status({ booking }: { booking: Booking }) {
  return (
    <Badge
      tone={
        booking.status === 'pending'
          ? 'rust'
          : booking.status === 'confirmed'
            ? 'blue'
            : booking.status === 'completed'
              ? 'green'
              : 'neutral'
      }
    >
      {booking.mentor_completed_at && booking.status === 'confirmed'
        ? 'Ждёт подтверждения студента'
        : booking.status_label}
    </Badge>
  );
}
export function LessonRow({
  booking: b,
  userId,
  navigate,
}: {
  booking: Booking;
  userId: number;
  navigate: Navigate;
}) {
  return (
    <button className="lesson-row" onClick={() => navigate('/lessons/' + b.id)}>
      <div className="lesson-date">
        <strong>
          {new Intl.DateTimeFormat('ru', { day: '2-digit', timeZone: 'Asia/Almaty' }).format(
            b.slot.starts_at * 1000,
          )}
        </strong>
        <span>
          {new Intl.DateTimeFormat('ru', { month: 'short', timeZone: 'Asia/Almaty' }).format(
            b.slot.starts_at * 1000,
          )}
        </span>
      </div>
      <div className="lesson-row-main">
        <Status booking={b} />
        {Boolean(b.unread_messages) && (
          <Badge tone="rust">
            {b.unread_messages} {b.unread_messages === 1 ? 'новое сообщение' : 'новых сообщ.'}
          </Badge>
        )}
        <h3>{b.topic}</h3>
        <p>
          {userId === b.mentor_id ? 'Студент: ' + b.student_name : 'Ментор: ' + b.mentor_name} ·{' '}
          {shortTime(b.slot.starts_at)}–{shortTime(b.slot.ends_at)}
        </p>
      </div>
      <span className="lesson-row-arrow">
        <ArrowUpRight size={21} />
      </span>
    </button>
  );
}
