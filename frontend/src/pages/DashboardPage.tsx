import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, clock, dateTime, money } from '../api';
import { MentorRow } from '../components/MentorRow';
import { LessonRow, active } from '../components/LessonStatus';
import type { Mentor, Navigate, Snapshot, ToggleFavorite } from '../types';
import { Empty } from '../ui';

export function DashboardPage({
  data,
  navigate,
  toggleFavorite,
}: {
  data: Snapshot;
  navigate: Navigate;
  toggleFavorite: ToggleFavorite;
}) {
  const [role, setRole] = useState(data.user.mentor ? 'mentor' : 'student'),
    [tab, setTab] = useState('upcoming'),
    [suggested, setSuggested] = useState<Mentor[] | null>(null);
  const favoriteIds = new Set(data.favorites.map((m) => m.id));
  const signals = data.progress.successful_tests + ':' + data.favorites.length;
  useEffect(() => {
    let alive = true;
    api<Mentor[]>('/recommendations')
      .then((rows) => alive && setSuggested(rows))
      .catch(() => alive && setSuggested([]));
    return () => {
      alive = false;
    };
  }, [signals]);
  const favoriteOf = (m: Mentor) => ({
    active: favoriteIds.has(m.id),
    toggle: (on: boolean) => toggleFavorite(m.id, on),
  });
  const own = data.bookings.filter((b) =>
    role === 'mentor' ? b.mentor_id === data.user.id : b.student_id === data.user.id,
  );
  const upcoming = own.filter(active).sort((a, b) => a.slot.starts_at - b.slot.starts_at),
    history = own.filter((b) => !active(b));
  const rows = tab === 'upcoming' ? upcoming : history;
  const next = upcoming.find(
    (b) => b.status === 'confirmed' && !b.mentor_completed_at && b.slot.starts_at > clock(),
  );
  return (
    <div className="content-page dashboard-page">
      <div className="page-heading dashboard-heading">
        <div>
          <span className="section-index">
            ЛИЧНОЕ / {role === 'mentor' ? 'ОБЪЯСНЯЮ ДРУГИМ' : 'УЧУСЬ САМ'}
          </span>
          <h1>
            {data.user.name.split(' ')[0]},<br />
            <em>{role === 'mentor' ? 'тебя ждут.' : 'всё получится.'}</em>
          </h1>
        </div>
        {data.user.mentor ? (
          <div className="role-switch" aria-label="Моя роль">
            <button aria-pressed={role === 'student'} onClick={() => setRole('student')}>
              Я учусь
            </button>
            <button aria-pressed={role === 'mentor'} onClick={() => setRole('mentor')}>
              Я объясняю
            </button>
          </div>
        ) : (
          <button className="button button-primary" onClick={() => navigate('/mentors')}>
            Найти помощь <ArrowUpRight size={18} />
          </button>
        )}
      </div>
      <div className="dashboard-summary">
        <div>
          <span className="mono">
            {role === 'mentor' ? 'ОЖИДАЮТ ТВОЕГО ОТВЕТА' : 'ОЖИДАЕМ МЕНТОРА'}
          </span>
          <strong>
            {upcoming
              .filter((b) => b.status === 'pending')
              .length.toString()
              .padStart(2, '0')}
          </strong>
        </div>
        <div>
          <span className="mono">ПОДТВЕРЖДЕНО В РАСПИСАНИИ</span>
          <strong>
            {upcoming
              .filter((b) => b.status === 'confirmed')
              .length.toString()
              .padStart(2, '0')}
          </strong>
        </div>
        <div>
          <span className="mono">ВСТРЕЧ ЗАВЕРШЕНО</span>
          <strong>
            {history
              .filter((b) => b.status === 'completed')
              .length.toString()
              .padStart(2, '0')}
          </strong>
        </div>
      </div>
      <div className="dashboard-layout">
        <section>
          <div className="section-title small-title">
            <h2>{role === 'mentor' ? 'Твои ученики' : 'Твои встречи'}</h2>
            <div className="text-tabs">
              <button aria-pressed={tab === 'upcoming'} onClick={() => setTab('upcoming')}>
                Активные
              </button>
              <button aria-pressed={tab === 'history'} onClick={() => setTab('history')}>
                История
              </button>
            </div>
          </div>
          {rows.length ? (
            <div className="lesson-list">
              {rows.map((b) => (
                <LessonRow key={b.id} booking={b} userId={data.user.id} navigate={navigate} />
              ))}
            </div>
          ) : (
            <Empty
              title={role === 'mentor' ? 'Новые вопросы ещё впереди' : 'Начни с одного вопроса'}
              text={
                role === 'mentor'
                  ? 'Проверь анкету и добавь свободное время. Когда студент отправит заявку, она появится здесь.'
                  : 'Выбери сложную тему и найди человека, который поможет её разобрать.'
              }
            >
              <button
                className="button button-outline"
                onClick={() => navigate(role === 'mentor' ? '/calendar' : '/mentors')}
              >
                {role === 'mentor' ? 'Открыть расписание' : 'Найти ментора'}
                <ArrowUpRight size={17} />
              </button>
            </Empty>
          )}
        </section>
        <aside className="dashboard-aside">
          {next ? (
            <div className="up-next-paper">
              <span className="mono">СЛЕДУЮЩАЯ ВСТРЕЧА</span>
              <h3>{next.topic}</h3>
              <p>
                {dateTime(next.slot.starts_at)}
                <br />
                {role === 'mentor' ? next.student_name : next.mentor_name}
              </p>
              <button
                className="button button-dark full"
                onClick={() => navigate('/lessons/' + next.id)}
              >
                К занятию <ArrowRight size={16} />
              </button>
            </div>
          ) : (
            <div className="margin-note">
              <span>✳</span>
              <h3>
                Вопрос не обязан
                <br />
                быть идеальным.
              </h3>
              <p>
                Можно прийти со своей попыткой, ошибкой в коде или одним непонятным определением.
              </p>
            </div>
          )}
          <button className="progress-link" onClick={() => navigate('/progress')}>
            <span className="mono">МОЙ ПРОГРЕСС</span>
            <strong>{data.progress.points} XP</strong>
            <span>
              Посмотреть, что уже получается <ArrowUpRight size={16} />
            </span>
          </button>
          {role === 'mentor' && data.user.mentor?.suspended && (
            <p className="field-error">
              Команда приостановила анкету. Новые заявки временно недоступны.
            </p>
          )}
        </aside>
      </div>
      {role === 'student' && suggested && suggested.length > 0 && (
        <section className="discover-section" aria-labelledby="suggested-title">
          <span className="section-index">ПОДОБРАНО ПО ТВОИМ ТЕСТАМ И ИНТЕРЕСАМ</span>
          <h2 id="suggested-title">Вам может подойти</h2>
          <div className="results-list">
            {suggested.slice(0, 3).map((m, i) => (
              <MentorRow
                key={m.id}
                mentor={m}
                index={i}
                disabled={false}
                open={() => navigate('/mentors/' + m.id)}
                favorite={favoriteOf(m)}
              />
            ))}
          </div>
        </section>
      )}
      {role === 'student' && data.favorites.length > 0 && (
        <section className="discover-section" aria-labelledby="favorites-title">
          <span className="section-index">СВОИ ЛЮДИ</span>
          <h2 id="favorites-title">Избранные</h2>
          <ul className="favorite-list">
            {data.favorites.map((m) => (
              <li key={m.id}>
                <button className="inline-link" onClick={() => navigate('/mentors/' + m.id)}>
                  {m.name}
                </button>
                <span className="muted">
                  {m.slots.length
                    ? 'Ближайшее: ' + dateTime(m.slots[0].starts_at)
                    : m.reasons[0] || 'Свободного времени пока нет'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {data.waitlist.length > 0 && (
        <section className="waiting-section">
          <h2>Запросы в листе ожидания</h2>
          {data.waitlist.map((w) => (
            <div className="data-row" key={w.id}>
              <strong>{w.topic}</strong>
              <span>До {dateTime(w.deadline)}</span>
              <span>до {money(w.budget)}</span>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
