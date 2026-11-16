import { ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { dateTime, money } from '../api';
import { LessonRow } from '../components/LessonStatus';
import { SubjectEditor } from '../components/SubjectEditor';
import type { Mutate, Navigate, Snapshot } from '../types';
import { Avatar, Empty, ErrorText } from '../ui';

export function TeamPage({
  data,
  mutate,
  working,
  navigate,
}: {
  data: Snapshot;
  mutate: Mutate;
  working: boolean;
  navigate: Navigate;
}) {
  const [error, setError] = useState('');
  if (!data.user.is_admin || !data.admin)
    return (
      <div className="content-page">
        <Empty title="Только для команды" text="Здесь находятся инструменты модерации кампуса." />
      </div>
    );
  const a = data.admin,
    s = a.stats;
  async function update(path: string, body: unknown) {
    setError('');
    try {
      await mutate(path, body, 'PUT');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="content-page team-page">
      <div className="page-heading">
        <span className="section-index">КОМАНДА / ПИЛОТ AITU</span>
        <h1>
          Как живёт
          <br />
          <em>наш кампус.</em>
        </h1>
        <p>Данные рассчитываются по заявкам. В режиме защиты они демонстрационные.</p>
      </div>
      <ErrorText message={error} />
      <div className="team-numbers">
        {[
          ['Заявок создано', s.total],
          ['Завершено', s.completion_rate == null ? '—' : s.completion_rate + '%'],
          [
            'Медиана ответа',
            s.median_confirmation_seconds == null
              ? '—'
              : Math.round(s.median_confirmation_seconds / 60) + ' мин',
          ],
          ['Студентов с повтором', s.repeat_rate == null ? '—' : s.repeat_rate + '%'],
        ].map(([label, value]) => (
          <div key={label}>
            <span className="mono">{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <details className="metrics-definition">
        <summary>
          Как считаются показатели <ChevronRight size={14} />
        </summary>
        {Object.values(s.definitions).map((t) => (
          <p key={t}>{t}</p>
        ))}
      </details>
      <section className="team-section">
        <div className="section-title small-title">
          <h2>Менторы и доверие</h2>
          <span className="mono">{a.mentors.length} АНКЕТ</span>
        </div>
        {a.mentors.map((m) => (
          <div className="moderation-row" key={m.id}>
            <Avatar name={m.name} id={m.id} />
            <div>
              <strong>{m.name}</strong>
              <small>
                {m.suspended
                  ? 'Приостановлен командой'
                  : m.active
                    ? 'Принимает заявки'
                    : 'Поставил личную паузу'}{' '}
                · {money(m.price)}
              </small>
            </div>
            <button
              className="button button-outline"
              disabled={working}
              onClick={() =>
                void update('/admin/mentors/' + m.id, {
                  verified: !m.verified,
                  active: !m.suspended,
                })
              }
            >
              {m.verified ? 'Снять проверку' : 'Подтвердить проверку'}
            </button>
            <button
              className="inline-link"
              disabled={working}
              onClick={() =>
                void update('/admin/mentors/' + m.id, { verified: m.verified, active: m.suspended })
              }
            >
              {m.suspended ? 'Восстановить' : 'Приостановить'}
            </button>
          </div>
        ))}
      </section>
      <section className="team-section">
        <h2>Каталог предметов</h2>
        {a.catalog.map((subject) => (
          <SubjectEditor
            key={subject.id}
            subject={subject}
            working={working}
            save={(body) => update('/admin/subjects/' + subject.id, body)}
          />
        ))}
      </section>
      <section className="team-section">
        <h2>Вопросы кампуса</h2>
        <div className="demand-list">
          {s.topics.map((t) => (
            <div key={t.topic}>
              <span>{t.topic}</span>
              <div>
                <i style={{ width: (s.total ? (t.count / s.total) * 100 : 0) + '%' }} />
              </div>
              <strong>{t.count}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="team-section">
        <h2>Все заявки</h2>
        {a.bookings.map((b) => (
          <LessonRow key={b.id} booking={b} userId={data.user.id} navigate={navigate} />
        ))}
      </section>
      <section className="team-section">
        <h2>Кому ещё нужна помощь</h2>
        {a.waitlist.length ? (
          a.waitlist.map((w, i) => (
            <div className="data-row" key={i}>
              <strong>
                {w.student} / {w.topic}
              </strong>
              <span>
                {money(w.budget)} · до {dateTime(w.deadline)}
              </span>
            </div>
          ))
        ) : (
          <p className="muted">Лист ожидания пока пуст.</p>
        )}
      </section>
    </div>
  );
}
