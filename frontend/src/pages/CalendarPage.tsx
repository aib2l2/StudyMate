import {
  ArrowUpRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Download,
  Plus,
  Repeat,
  X,
} from 'lucide-react';
import { useState } from 'react';
import {
  clock,
  dateInput,
  dateOnly,
  dateTime,
  download,
  parseInput,
  plural,
  shortTime,
  topicsOf,
} from '../api';
import { LessonRow, active } from '../components/LessonStatus';
import type { Mutate, Navigate, SeriesResult, Snapshot } from '../types';
import { Badge, Empty, ErrorText } from '../ui';

export function CalendarPage({
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
  const today = Math.floor((clock() + 18000) / 86400) * 86400 - 18000;
  const [offset, setOffset] = useState(0),
    [day, setDay] = useState(dateInput(today).slice(0, 10)),
    [slotStart, setSlotStart] = useState(dateInput(Math.ceil((clock() + 7200) / 1800) * 1800)),
    [error, setError] = useState(''),
    [showClosed, setShowClosed] = useState(false),
    [weekly, setWeekly] = useState(false),
    [weeks, setWeeks] = useState(4),
    [report, setReport] = useState(''),
    [isGroup, setIsGroup] = useState(false),
    [group, setGroup] = useState({
      capacity: 4,
      topic_id: data.user.mentor?.topic_ids[0] ?? 0,
      price: Math.round(((data.user.mentor?.price ?? 2500) * 0.5) / 100) * 100,
      format: 'online',
      meeting_url: '',
      meeting_place: '',
      min_participants: 2,
    });
  const myTopics = topicsOf(data.catalog).filter((t) => data.user.mentor?.topic_ids.includes(t.id));
  const days = Array.from({ length: 7 }, (_, i) => today + (i + offset * 7) * 86400),
    rows = data.bookings.filter((b) => active(b) && dateInput(b.slot.starts_at).startsWith(day));
  const slots = data.slots.filter(
    (s) => dateInput(s.starts_at).startsWith(day) && (showClosed || s.enabled),
  );
  async function cancelGroup(id: number) {
    setError('');
    try {
      const result = await mutate<{ message: string }>(`/mentor/slots/${id}/cancel`, {});
      setReport('Групповое занятие отменено. ' + (result.message || ''));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function closeSeries(id: string) {
    setError('');
    try {
      const result = await mutate<{ closed: number; kept_with_bookings: number }>(
        '/mentor/series/' + id,
        {},
        'DELETE',
      );
      setReport(
        `Закрыто будущих интервалов серии: ${result.closed}.` +
          (result.kept_with_bookings ? ` С записями оставлено: ${result.kept_with_bookings}.` : ''),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function closeSlot(id: number) {
    setError('');
    try {
      await mutate('/mentor/slots/' + id, {}, 'DELETE');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="content-page calendar-page">
      <div className="page-heading">
        <span className="section-index">РАСПИСАНИЕ / АЛМАТЫ, UTC+5</span>
        <h1>
          Время
          <br />
          <em>разобраться.</em>
        </h1>
        <p>Свободное время и подтверждённые встречи показаны отдельно.</p>
        <button
          className="inline-link"
          onClick={() =>
            void download('/calendar.ics', 'studymate.ics').catch((e) => setError(e.message))
          }
        >
          Все подтверждённые встречи в календарь (.ics) <Download size={15} />
        </button>
      </div>
      <div className="calendar-toolbar">
        <h2>
          {dateOnly(days[0])} — {dateOnly(days[6])}
        </h2>
        <div>
          <button
            className="icon-button"
            onClick={() => {
              setOffset(offset - 1);
              setDay(dateInput(parseInput(day + 'T00:00') - 7 * 86400).slice(0, 10));
            }}
            aria-label="Предыдущая неделя"
          >
            <ChevronLeft />
          </button>
          <button
            className="icon-button"
            onClick={() => {
              setOffset(offset + 1);
              setDay(dateInput(parseInput(day + 'T00:00') + 7 * 86400).slice(0, 10));
            }}
            aria-label="Следующая неделя"
          >
            <ChevronRight />
          </button>
        </div>
      </div>
      <div className="week-strip">
        {days.map((timestamp) => {
          const key = dateInput(timestamp).slice(0, 10),
            count = data.bookings.filter(
              (b) => active(b) && dateInput(b.slot.starts_at).startsWith(key),
            ).length;
          return (
            <button key={timestamp} aria-pressed={day === key} onClick={() => setDay(key)}>
              <span>
                {new Intl.DateTimeFormat('ru', {
                  weekday: 'short',
                  timeZone: 'Asia/Almaty',
                }).format(timestamp * 1000)}
              </span>
              <strong>
                {new Intl.DateTimeFormat('ru', { day: '2-digit', timeZone: 'Asia/Almaty' }).format(
                  timestamp * 1000,
                )}
              </strong>
              <small>
                {count ? `${count} ${plural(count, ['встреча', 'встречи', 'встреч'])}` : '—'}
              </small>
            </button>
          );
        })}
      </div>
      <ErrorText message={error} />
      {report && (
        <p className="success-note" role="status">
          {report}
        </p>
      )}
      <div className="calendar-layout">
        <section>
          <div className="section-title small-title">
            <h2>Занятия в этот день</h2>
            <CalendarDays size={21} />
          </div>
          {rows.length ? (
            rows.map((b) => (
              <LessonRow key={b.id} booking={b} userId={data.user.id} navigate={navigate} />
            ))
          ) : (
            <Empty title="День свободен" text="Когда запись будет создана, она появится здесь." />
          )}
          {data.user.mentor && (
            <section className="availability-section">
              <h2>Интервалы ментора</h2>
              <label className="check-option">
                <input
                  type="checkbox"
                  checked={showClosed}
                  onChange={(e) => setShowClosed(e.target.checked)}
                />
                Показать закрытые интервалы
              </label>
              <div className="availability-list">
                {slots.map((s) => (
                  <div key={s.id} className={'availability-row availability-' + s.state}>
                    <strong>
                      {shortTime(s.starts_at)}–{shortTime(s.ends_at)}
                    </strong>
                    <Badge
                      tone={
                        s.state === 'confirmed'
                          ? 'blue'
                          : s.state === 'pending'
                            ? 'rust'
                            : 'neutral'
                      }
                    >
                      {
                        {
                          free: 'Свободно',
                          pending: 'Ожидает ответа',
                          confirmed: 'Занято',
                          completed: 'Состоялось',
                          closed: 'Закрыто',
                          group: `Группа · ${s.taken ?? 0} из ${s.capacity}`,
                        }[s.state || 'free']
                      }
                    </Badge>
                    {s.student && <span>{s.student}</span>}
                    {Boolean(s.students?.length) && <span>{s.students!.join(', ')}</span>}
                    {s.state === 'group' && s.starts_at > clock() && (
                      <button
                        className="inline-link"
                        disabled={working}
                        onClick={() => void cancelGroup(s.id)}
                      >
                        Отменить группу <X size={14} />
                      </button>
                    )}
                    {s.series_id && (
                      <span className="series-mark" title="Повторяется каждую неделю">
                        <Repeat size={13} /> серия
                      </span>
                    )}
                    {s.series_id && s.state === 'free' && (
                      <button
                        className="inline-link"
                        disabled={working}
                        onClick={() => void closeSeries(s.series_id!)}
                      >
                        Закрыть всю серию
                      </button>
                    )}
                    {s.state === 'free' && (
                      <button
                        className="inline-link"
                        disabled={working}
                        onClick={() => void closeSlot(s.id)}
                      >
                        Закрыть <X size={14} />
                      </button>
                    )}
                    {s.state === 'closed' && (
                      <button
                        className="inline-link"
                        disabled={working}
                        onClick={async () => {
                          setError('');
                          try {
                            await mutate('/mentor/slots', { starts_at: s.starts_at });
                          } catch (e) {
                            setError((e as Error).message);
                          }
                        }}
                      >
                        Открыть <Plus size={14} />
                      </button>
                    )}
                    {s.booking_id && (
                      <button
                        className="inline-link"
                        onClick={() => navigate('/lessons/' + s.booking_id)}
                      >
                        К записи <ArrowUpRight size={14} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
              {!slots.length && <p className="muted">На этот день интервалы не добавлены.</p>}
            </section>
          )}
        </section>
        <aside>
          {data.user.mentor ? (
            <form
              className="schedule-paper"
              onSubmit={async (e) => {
                e.preventDefault();
                setError('');
                setReport('');
                try {
                  const start = parseInput(slotStart);
                  const groupFields = isGroup
                    ? {
                        ...group,
                        meeting_url: group.format === 'online' ? group.meeting_url : null,
                        meeting_place: group.format === 'campus' ? group.meeting_place : null,
                      }
                    : null;
                  if (weekly) {
                    const result = await mutate<SeriesResult>('/mentor/slots/series', {
                      starts_at: start,
                      weeks,
                      group: groupFields,
                    });
                    setReport(
                      `Добавлено интервалов: ${result.created.length}.` +
                        (result.skipped.length
                          ? ' Пропущено: ' +
                            result.skipped
                              .map((x) => `${dateTime(x.starts_at)} — ${x.reason.toLowerCase()}`)
                              .join('; ')
                          : ''),
                    );
                  } else if (groupFields)
                    await mutate('/mentor/slots/group', { starts_at: start, ...groupFields });
                  else await mutate('/mentor/slots', { starts_at: start });
                  setDay(dateInput(start).slice(0, 10));
                  setOffset(Math.floor((start - today) / (7 * 86400)));
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              <span className="mono">ТВОЁ СВОБОДНОЕ ВРЕМЯ</span>
              <h3>Открой новый интервал.</h3>
              <label className="field">
                Начало · Алматы
                <input
                  type="datetime-local"
                  value={slotStart}
                  onChange={(e) => setSlotStart(e.target.value)}
                  required
                />
              </label>
              <label className="check-option">
                <input
                  type="checkbox"
                  checked={isGroup}
                  onChange={(e) => setIsGroup(e.target.checked)}
                />
                Групповое занятие (2–5 человек)
              </label>
              {isGroup && (
                <fieldset className="group-fields">
                  <legend>Группа</legend>
                  <label className="field">
                    Тема
                    <select
                      value={group.topic_id}
                      onChange={(e) => setGroup({ ...group, topic_id: Number(e.target.value) })}
                    >
                      {myTopics.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="form-pair">
                    <label className="field">
                      Мест
                      <input
                        type="number"
                        min={2}
                        max={5}
                        value={group.capacity}
                        onChange={(e) => setGroup({ ...group, capacity: Number(e.target.value) })}
                      />
                    </label>
                    <label className="field">
                      Минимум
                      <input
                        type="number"
                        min={1}
                        max={group.capacity}
                        value={group.min_participants}
                        onChange={(e) =>
                          setGroup({ ...group, min_participants: Number(e.target.value) })
                        }
                      />
                    </label>
                  </div>
                  <label className="field">
                    Цена за место, ₸
                    <input
                      type="number"
                      min={0}
                      max={100000}
                      step={100}
                      value={group.price}
                      onChange={(e) => setGroup({ ...group, price: Number(e.target.value) })}
                    />
                  </label>
                  <label className="field">
                    Формат
                    <select
                      value={group.format}
                      onChange={(e) => setGroup({ ...group, format: e.target.value })}
                    >
                      <option value="online">Онлайн</option>
                      <option value="campus">На кампусе</option>
                    </select>
                  </label>
                  {group.format === 'online' ? (
                    <label className="field">
                      Ссылка на встречу (HTTPS)
                      <input
                        type="url"
                        value={group.meeting_url}
                        placeholder="https://…"
                        onChange={(e) => setGroup({ ...group, meeting_url: e.target.value })}
                        required
                      />
                    </label>
                  ) : (
                    <label className="field">
                      Аудитория
                      <input
                        value={group.meeting_place}
                        onChange={(e) => setGroup({ ...group, meeting_place: e.target.value })}
                        required
                      />
                    </label>
                  )}
                  <p className="micro">
                    Студенты записываются сразу, без подтверждения. Если за 2 часа до начала
                    участников меньше минимума, занятие отменится автоматически.
                  </p>
                </fieldset>
              )}
              <label className="check-option">
                <input
                  type="checkbox"
                  checked={weekly}
                  onChange={(e) => setWeekly(e.target.checked)}
                />
                Повторять каждую неделю
              </label>
              {weekly && (
                <label className="field">
                  Сколько недель
                  <input
                    type="number"
                    min={2}
                    max={12}
                    value={weeks}
                    onChange={(e) => setWeeks(Number(e.target.value))}
                  />
                </label>
              )}
              <p className="micro">
                Занятие длится 30 минут. Пересечения с другими встречами проверим автоматически;
                неделя с пересечением будет пропущена, остальные — добавлены.
              </p>
              <button className="button button-primary full" disabled={working}>
                {weekly
                  ? `Добавить серию на ${weeks} нед.`
                  : isGroup
                    ? 'Открыть группу'
                    : 'Добавить время'}{' '}
                <Plus size={17} />
              </button>
            </form>
          ) : (
            <div className="margin-note">
              <span>↗</span>
              <h3>
                Забронируй
                <br />
                полчаса для себя.
              </h3>
              <p>Здесь будет твоё расписание встреч с менторами.</p>
              <button className="inline-link" onClick={() => navigate('/mentors')}>
                Найти помощь <ArrowUpRight size={17} />
              </button>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
