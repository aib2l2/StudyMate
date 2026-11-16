import { ArrowUpRight, CalendarDays, ShieldCheck, Star } from 'lucide-react';
import { dateTime, languages, money } from '../api';
import type { Mentor } from '../types';
import { Avatar, CheckText } from '../ui';
import { FavoriteButton } from './FavoriteButton';

export function MentorRow({
  mentor: m,
  index,
  disabled,
  open,
  favorite,
}: {
  mentor: Mentor;
  index: number;
  disabled: boolean;
  open: () => void;
  favorite?: { active: boolean; toggle: (on: boolean) => Promise<unknown> };
}) {
  return (
    <article className="mentor-row">
      <div className="mentor-identity">
        <span className="mono row-number">{String(index + 1).padStart(2, '0')}</span>
        <Avatar name={m.name} id={m.id} large />
        <div>
          <h2>
            {m.name}
            {favorite && <FavoriteButton name={m.name} {...favorite} />}
          </h2>
          <p>{m.course} курс / Astana IT University</p>
          <div className="trust-line">
            {m.verified && (
              <span>
                <ShieldCheck size={13} />
                Проверен командой
              </span>
            )}
            <span>
              <Star size={13} />
              {m.rating ?? 'Пока без отзывов'}
              {m.review_count > 0 ? ` · ${m.review_count} отз.` : ''}
            </span>
          </div>
        </div>
      </div>
      <p className="mentor-bio">{m.bio}</p>
      <div className="topic-line">
        {m.topics.slice(0, 3).map((t) => (
          <span key={t.id}>{t.name}</span>
        ))}
      </div>
      <div className="row-lower">
        <div>
          <span className="mono">БЛИЖАЙШЕЕ ВРЕМЯ</span>
          <p>
            <CalendarDays size={14} />
            {dateTime(m.slots[0].starts_at)}
          </p>
        </div>
        <div className="row-price">
          <strong>{money(m.price)}</strong>
          <small>30 минут / {m.languages.map((l) => languages[l]).join(', ')}</small>
        </div>
        <button className="button button-outline" disabled={disabled} onClick={open}>
          Познакомиться <ArrowUpRight size={17} />
        </button>
      </div>
      <div className="reasons-line">
        {m.reasons.slice(0, 3).map((r) => (
          <CheckText key={r}>{r}</CheckText>
        ))}
      </div>
    </article>
  );
}
