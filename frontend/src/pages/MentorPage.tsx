import { ArrowLeft, ArrowUpRight, CalendarDays, ShieldCheck, Star } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  api,
  clock,
  dateTime,
  languages,
  money,
  parseFilters,
  plural,
  queryOf,
  topicsOf,
} from '../api';
import { BookingDialog } from '../components/BookingDialog';
import type { Slot, Booking, Mentor, Mutate, Navigate, Subject, User } from '../types';
import { FavoriteButton } from '../components/FavoriteButton';
import { Avatar, Badge, Busy, ErrorText } from '../ui';

export function MentorPage({
  id,
  catalog,
  query,
  navigate,
  user,
  mutate,
  working,
  favorite,
}: {
  favorite?: { active: boolean; toggle: (on: boolean) => Promise<unknown> };
  id: number;
  catalog: Subject[];
  query: string;
  navigate: Navigate;
  user: User | null;
  mutate: Mutate;
  working: boolean;
}) {
  const [mentor, setMentor] = useState<Mentor | null>(null),
    [error, setError] = useState(''),
    [selectedSlot, setSelectedSlot] = useState<number | null>(null),
    [topicId, setTopicId] = useState(0);
  const signature = topicsOf(catalog)
    .map((t) => t.id)
    .join(',');
  const filters = useMemo(() => parseFilters(query, catalog), [query, signature]);
  useEffect(() => {
    let alive = true;
    setError('');
    setMentor(null);
    setSelectedSlot(null);
    api<Mentor>('/public/mentors/' + id)
      .then((m) => {
        if (alive) {
          setMentor(m);
          setTopicId(
            m.topic_ids.includes(filters.topic_id)
              ? filters.topic_id
              : m.topic_ids.find((t) => topicsOf(catalog).some((x) => x.id === t)) || 0,
          );
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [id, signature]);
  if (error)
    return (
      <div className="content-page">
        <ErrorText message={error} />
        <button className="inline-link" onClick={() => navigate('/mentors')}>
          Вернуться к поиску <ArrowLeft size={17} />
        </button>
      </div>
    );
  if (!mentor) return <Busy />;
  const slots = mentor.slots.filter(
    (s) => s.starts_at >= Math.max(filters.earliest, clock() + 60) && s.ends_at <= filters.deadline,
  );
  const eligible =
    mentor.price <= filters.budget &&
    mentor.languages.includes(filters.language) &&
    mentor.formats.includes(filters.format) &&
    Boolean(topicId) &&
    user?.id !== mentor.id;
  // Group seats have their own topic, price and format.
  const seatOk = (s: Slot) =>
    (s.capacity ?? 1) > 1
      ? (s.price ?? 0) <= filters.budget &&
        mentor.languages.includes(filters.language) &&
        user?.id !== mentor.id
      : eligible;
  return (
    <div className="content-page mentor-profile">
      <a
        className="back-link"
        href={'/mentors?' + queryOf(filters)}
        onClick={(e) => {
          e.preventDefault();
          navigate('/mentors?' + queryOf(filters));
        }}
      >
        <ArrowLeft size={16} />К результатам поиска
      </a>
      <div className="mentor-profile-grid">
        <section>
          <span className="section-index">СВОЙ ЧЕЛОВЕК / AITU</span>
          <div className="profile-name">
            <Avatar name={mentor.name} id={mentor.id} large />
            <div>
              <h1>
                Привет,
                <br />я <em>{mentor.name}.</em>
              </h1>
              {favorite && <FavoriteButton name={mentor.name} {...favorite} />}
              <p>
                {mentor.course} курс / {mentor.languages.map((l) => languages[l]).join(' · ')}
              </p>
            </div>
          </div>
          <div className="profile-badges">
            {mentor.verified && (
              <Badge tone="blue">
                <ShieldCheck size={14} />
                Проверен командой
              </Badge>
            )}
            <Badge>
              <Star size={14} />
              {mentor.rating ?? 'Без оценки'} · {mentor.review_count}{' '}
              {plural(mentor.review_count, ['отзыв', 'отзыва', 'отзывов'])}
            </Badge>
          </div>
          <section className="profile-section">
            <h2>Как я помогаю</h2>
            <p>{mentor.bio}</p>
          </section>
          <section className="profile-section">
            <h2>Мои сильные темы</h2>
            <div className="topic-line">
              {mentor.topics
                .filter((t) => topicsOf(catalog).some((x) => x.id === t.id))
                .map((t) => (
                  <span key={t.id}>{t.name}</span>
                ))}
            </div>
          </section>
          <section className="profile-section">
            <div className="section-title small-title">
              <h2>После встреч</h2>
              <span className="mono">ОТЗЫВЫ СТУДЕНТОВ</span>
            </div>
            {mentor.reviews?.length ? (
              mentor.reviews.map((r, i) => (
                <article className="review-quote" key={i}>
                  <p>«{r.comment}»</p>
                  <div>
                    <strong>{r.student}</strong>
                    <span>
                      <Star size={13} />
                      {r.rating}/5
                    </span>
                  </div>
                </article>
              ))
            ) : (
              <p className="muted">Пока нет отзывов. Первый появится после завершённого занятия.</p>
            )}
          </section>
        </section>
        <aside className="booking-paper">
          <div className="note-top">
            <span className="mono">ОДНА ТЕМА / ОДНА ВСТРЕЧА</span>
            <span>↗</span>
          </div>
          <div className="big-price">
            {money(mentor.price)}
            <small>за 30 минут</small>
          </div>
          <label className="field">
            Что разбираем?
            <select value={topicId} onChange={(e) => setTopicId(Number(e.target.value))}>
              {mentor.topics
                .filter((t) => topicsOf(catalog).some((x) => x.id === t.id))
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
            </select>
          </label>
          <div className="schedule-label">
            <CalendarDays size={16} />
            <span>Свободное время / Алматы</span>
          </div>
          <div className="profile-slots">
            {slots.slice(0, 12).map((s) => (
              <button
                className={'slot-button' + ((s.capacity ?? 1) > 1 ? ' slot-group' : '')}
                key={s.id}
                disabled={!seatOk(s)}
                onClick={() => {
                  if (!user) {
                    navigate(
                      '/login?next=' +
                        encodeURIComponent('/mentors/' + id + '?' + queryOf(filters)),
                    );
                    return;
                  }
                  setSelectedSlot(s.id);
                }}
              >
                {dateTime(s.starts_at)}
                {(s.capacity ?? 1) > 1 && (
                  <small>
                    Группа · занято {s.taken ?? 0} из {s.capacity} · {money(s.price ?? 0)} за место
                    {s.format === 'campus' ? ' · кампус' : ' · онлайн'}
                  </small>
                )}
                <ArrowUpRight size={15} />
              </button>
            ))}
          </div>
          {!slots.length && (
            <p className="muted">
              В заданный интервал свободного времени нет. Измени условия поиска.
            </p>
          )}
          {!eligible && !slots.some(seatOk) && (
            <p className="field-error">
              {user?.id === mentor.id
                ? 'Это твоя анкета. Записаться можно к другому ментору.'
                : 'Цена, язык или формат не совпадают с условиями поиска.'}
            </p>
          )}
          <button className="inline-link" onClick={() => navigate('/mentors?' + queryOf(filters))}>
            Изменить условия <ArrowUpRight size={15} />
          </button>
          <div className="booking-footnote">
            <ShieldCheck size={18} />
            <p>
              Сначала заявка, затем подтверждение. Ссылка или место встречи появятся на странице
              занятия.
            </p>
          </div>
        </aside>
      </div>
      {selectedSlot && user && (
        <BookingDialog
          mentor={mentor}
          slotId={selectedSlot}
          topicId={topicId}
          filters={filters}
          close={() => setSelectedSlot(null)}
          working={working}
          submit={async (body) => {
            const b = await mutate<Booking>('/bookings', body);
            navigate('/lessons/' + b.id);
          }}
        />
      )}
    </div>
  );
}
