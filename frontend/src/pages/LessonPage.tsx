import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  ChevronRight,
  ExternalLink,
  MapPin,
  Star,
  Video,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, clock, dateTime, money } from '../api';
import { ChatPanel } from '../components/ChatPanel';
import { ReschedulePanel } from '../components/ReschedulePanel';
import { Status, active } from '../components/LessonStatus';
import type { Booking, Mutate, Navigate, Snapshot } from '../types';
import { Avatar, Busy, ErrorText, Modal } from '../ui';

export function LessonPage({
  id,
  data,
  navigate,
  mutate,
  working,
  demo,
  practice,
}: {
  id: string;
  data: Snapshot;
  navigate: Navigate;
  mutate: Mutate;
  working: boolean;
  demo: boolean;
  practice: (topic: number, stage: string) => void;
}) {
  const [lesson, setLesson] = useState<Booking | null>(null),
    [error, setError] = useState(''),
    [note, setNote] = useState(''),
    [meetingUrl, setMeetingUrl] = useState(''),
    [meetingPlace, setMeetingPlace] = useState(''),
    [materials, setMaterials] = useState(''),
    [saved, setSaved] = useState(''),
    [reviewOpen, setReviewOpen] = useState(false),
    [rating, setRating] = useState(5),
    [comment, setComment] = useState('');
  const initialized = useRef('');
  const load = async () => {
    const b = await api<Booking>('/bookings/' + id);
    setLesson(b);
    if (initialized.current !== id) {
      setNote(b.notes || '');
      setMeetingUrl(b.meeting_url);
      setMeetingPlace(b.meeting_place);
      setMaterials(b.materials);
      initialized.current = id;
    }
  };
  const incoming = data.bookings.find((b) => b.id === id);
  useEffect(() => {
    setError('');
    void load().catch((e) => setError(e.message));
  }, [
    id,
    incoming?.status,
    incoming?.mentor_completed_at,
    incoming?.materials,
    incoming?.meeting_url,
    incoming?.meeting_place,
    incoming?.slot.id,
    incoming?.reschedule?.id,
    incoming?.group?.taken,
  ]);
  async function action(action: string, details: Record<string, unknown> = {}) {
    setError('');
    try {
      await mutate('/bookings/' + id + '/action', { action, ...details });
      await load();
      setSaved('Статус обновлён');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function saveWorkspace(body: unknown, message: string) {
    setError('');
    try {
      await mutate('/bookings/' + id + '/workspace', body, 'PUT');
      await load();
      setSaved(message);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!lesson)
    return (
      <div className="content-page">
        <ErrorText message={error} />
        {!error && <Busy />}
      </div>
    );
  const b = lesson,
    isMentor = b.mentor_id === data.user.id,
    isStudent = b.student_id === data.user.id;
  const room = b.format === 'online' ? b.meeting_url : b.meeting_place;
  return (
    <div className="content-page lesson-page">
      <a
        className="back-link"
        href="/dashboard"
        onClick={(e) => {
          e.preventDefault();
          navigate('/dashboard');
        }}
      >
        <ArrowLeft size={16} />К моим встречам
      </a>
      <div className="lesson-title">
        <div>
          <span className="section-index">ВСТРЕЧА / {b.id.slice(0, 8).toUpperCase()}</span>
          <h1>
            {b.topic}
            <em> — разберём.</em>
          </h1>
          <div className="lesson-heading-meta">
            <Status booking={b} />
            <span>{dateTime(b.slot.starts_at)} · 30 минут</span>
            <span>{b.format === 'online' ? 'Онлайн' : 'На кампусе'}</span>
            {b.group && (
              <span>
                Группа · {b.group.taken} из {b.group.capacity}
              </span>
            )}
          </div>
          {b.group && <p className="group-line">Участники: {b.group.participants.join(', ')}</p>}
        </div>
        <div className="lesson-price">
          {money(b.price)}
          <small>Стоимость встречи</small>
        </div>
      </div>
      <ErrorText message={error} />
      {saved && (
        <p className="success-note" role="status">
          {saved}
        </p>
      )}
      <div className="lesson-workspace">
        <section>
          <div className="meeting-sheet">
            <div className="sheet-label">
              <span className="mono">01 / ВСТРЕЧАЕМСЯ ЗДЕСЬ</span>
              {b.format === 'online' ? <Video size={21} /> : <MapPin size={21} />}
            </div>
            {b.status === 'pending' ? (
              <>
                <h2>Сначала договоримся.</h2>
                <p>
                  {isMentor
                    ? 'Проверь запрос и укажи ссылку на звонок или аудиторию перед подтверждением.'
                    : 'Ментор ещё проверяет время. После подтверждения здесь появится ссылка или место.'}
                </p>
                <p className="micro">Ответ до {dateTime(b.expires_at)}</p>
              </>
            ) : room ? (
              <>
                <h2>{b.format === 'online' ? 'До встречи по ссылке.' : b.meeting_place}</h2>
                {b.format === 'online' && (
                  <a
                    className="button button-dark"
                    href={b.meeting_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Открыть встречу <ExternalLink size={17} />
                  </a>
                )}
                <p className="micro">
                  {b.format === 'online' ? b.meeting_url : 'Место указал ментор. Время по Алматы.'}
                </p>
              </>
            ) : (
              <>
                <h2>Место ещё не добавлено.</h2>
                <p>
                  Ментор должен обновить данные встречи. Это запись из предыдущей версии проекта.
                </p>
              </>
            )}
            <div className="meeting-person">
              <Avatar
                name={isMentor ? b.student_name : b.mentor_name}
                id={isMentor ? b.student_id : b.mentor_id}
              />
              <span>
                <strong>{isMentor ? b.student_name : b.mentor_name}</strong>
                <small>{isMentor ? 'Твой студент' : 'Твой ментор'}</small>
              </span>
            </div>
          </div>
          <section className="lesson-section">
            <span className="mono">02 / ЧТО РАЗБИРАЕМ</span>
            <h2>Вопрос на эту встречу</h2>
            <p className="preserve-lines">
              {b.description || 'Обсудите цель встречи в начале занятия.'}
            </p>
          </section>
          <section className="lesson-section">
            <div className="section-title small-title">
              <div>
                <span className="mono">03 / ОСТАВИМ ПОД РУКОЙ</span>
                <h2>Материалы</h2>
              </div>
              <BookOpen size={22} />
            </div>
            {b.materials ? (
              <div className="materials-list">
                {b.materials.split('\n').map((line, i) =>
                  /^https:\/\/\S+$/.test(line.trim()) ? (
                    <a key={i} href={line.trim()} target="_blank" rel="noreferrer">
                      {line}
                      <ArrowUpRight size={15} />
                    </a>
                  ) : (
                    <p key={i}>{line}</p>
                  ),
                )}
              </div>
            ) : (
              <p className="muted">Здесь появятся ссылки, примеры и задания от ментора.</p>
            )}
          </section>
          <section className="lesson-section">
            <span className="mono">04 / СВОИМИ СЛОВАМИ</span>
            <h2>Мои заметки</h2>
            <p className="micro">Видны только тебе. У другого участника — свой блокнот.</p>
            {(isStudent || isMentor) && (
              <form
                className="notes-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void saveWorkspace({ notes: note }, 'Личные заметки сохранены');
                }}
              >
                <textarea
                  aria-label="Мои заметки"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={20000}
                  rows={7}
                  placeholder="Что стало понятнее? Какой пример стоит повторить?"
                />
                <button className="button button-outline" disabled={working}>
                  Сохранить заметки <Check size={16} />
                </button>
              </form>
            )}
          </section>
          {(isStudent || isMentor) && <ChatPanel bookingId={b.id} userId={data.user.id} />}
        </section>
        <aside className="lesson-sidebar">
          {(isStudent || isMentor) && (
            <ReschedulePanel booking={b} userId={data.user.id} mutate={mutate} working={working} />
          )}
          {isMentor && active(b) && (
            <form
              className="mentor-meeting-form"
              onSubmit={(e) => {
                e.preventDefault();
                if (b.status === 'pending')
                  void action('confirm', { meeting_url: meetingUrl, meeting_place: meetingPlace });
                else
                  void saveWorkspace(
                    { meeting_url: meetingUrl, meeting_place: meetingPlace, materials },
                    'Данные встречи сохранены',
                  );
              }}
            >
              <span className="mono">ДЛЯ МЕНТОРА</span>
              <h3>{b.status === 'pending' ? 'Подтвердить встречу' : 'Данные встречи'}</h3>
              {b.format === 'online' ? (
                <label className="field">
                  Ссылка на звонок
                  <input
                    type="url"
                    value={meetingUrl}
                    onChange={(e) => setMeetingUrl(e.target.value)}
                    required
                    placeholder="https://…"
                  />
                </label>
              ) : (
                <label className="field">
                  Где встречаемся?
                  <input
                    value={meetingPlace}
                    onChange={(e) => setMeetingPlace(e.target.value)}
                    required
                    maxLength={500}
                    placeholder="Корпус, этаж, аудитория"
                  />
                </label>
              )}
              {b.status === 'confirmed' && (
                <label className="field">
                  Материалы и ссылки
                  <textarea
                    rows={4}
                    value={materials}
                    onChange={(e) => setMaterials(e.target.value)}
                    maxLength={10000}
                    placeholder="Одна ссылка или заметка на строку"
                  />
                </label>
              )}
              <button className="button button-primary full" disabled={working}>
                {b.status === 'pending' ? 'Подтвердить заявку' : 'Сохранить данные'}
                <Check size={17} />
              </button>
              {b.status === 'pending' && (
                <button
                  type="button"
                  className="inline-link"
                  disabled={working}
                  onClick={() => void action('reject')}
                >
                  Не смогу в это время
                </button>
              )}
            </form>
          )}
          <div className="lesson-checkpoint">
            <span className="mono">ПРОВЕРКА ПОНИМАНИЯ</span>
            <h3>Что уже получается?</h3>
            <p>Можно пройти короткий тест по теме до и после встречи.</p>
            {isStudent && active(b) && (
              <button
                className="button button-outline full"
                onClick={() => practice(b.topic_id, 'pre')}
              >
                {b.quizzes.pre?.score != null
                  ? `До встречи: ${b.quizzes.pre.score}/3`
                  : 'Тест до встречи'}
                <ArrowUpRight size={16} />
              </button>
            )}
            {isStudent && b.status === 'completed' && (
              <button
                className="button button-primary full"
                onClick={() => practice(b.topic_id, 'post')}
              >
                {b.quizzes.post?.score != null
                  ? `После встречи: ${b.quizzes.post.score}/3`
                  : 'Тест после встречи'}
                <ArrowUpRight size={16} />
              </button>
            )}
            {b.quizzes.pre?.score != null && b.quizzes.post?.score != null && (
              <div className="test-comparison">
                <span>
                  До<strong>{b.quizzes.pre.score}/3</strong>
                </span>
                <ArrowRight size={17} />
                <span>
                  После<strong>{b.quizzes.post.score}/3</strong>
                </span>
              </div>
            )}
          </div>
          {b.status === 'confirmed' && (
            <div className="completion-box">
              <span className="mono">КОГДА РАЗОБРАЛИСЬ</span>
              {isMentor ? (
                <>
                  <h3>
                    {b.mentor_completed_at ? 'Студент подтвердит итог.' : 'Отметь завершение.'}
                  </h3>
                  <p>
                    {b.mentor_completed_at
                      ? 'Участнику отправлено уведомление. После его подтверждения появится отзыв.'
                      : 'После встречи студент подтвердит, что занятие состоялось.'}
                  </p>
                  {!b.mentor_completed_at && (clock() >= b.slot.ends_at || demo) && (
                    <button
                      className={
                        'button full ' +
                        (demo && clock() < b.slot.ends_at ? 'button-demo' : 'button-dark')
                      }
                      disabled={working}
                      onClick={() => void action('request_completion')}
                    >
                      {demo && clock() < b.slot.ends_at
                        ? 'Демо: встреча завершена'
                        : 'Встреча завершена'}
                      <CheckCheck size={17} />
                    </button>
                  )}
                </>
              ) : isStudent && b.mentor_completed_at ? (
                <>
                  <h3>Встреча состоялась?</h3>
                  <p>Ментор отметил завершение. Подтверди, если вы провели занятие.</p>
                  <button
                    className="button button-primary full"
                    disabled={working}
                    onClick={() => void action('complete')}
                  >
                    Подтверждаю завершение <CheckCheck size={17} />
                  </button>
                </>
              ) : (
                <>
                  <h3>Встреча впереди.</h3>
                  <p>
                    После занятия ментор отметит завершение, а ты сможешь подтвердить его и оставить
                    отзыв.
                  </p>
                </>
              )}
            </div>
          )}
          {b.status === 'completed' && (
            <div className="completed-paper">
              <span className="completion-stamp">СОСТОЯЛОСЬ ✓</span>
              <h3>Ещё один понятный шаг.</h3>
              {b.review ? (
                <blockquote>
                  «{b.review.comment}»
                  <span>
                    <Star size={13} />
                    {b.review.rating}/5
                  </span>
                </blockquote>
              ) : (
                isStudent && (
                  <button
                    className="button button-outline full"
                    onClick={() => setReviewOpen(true)}
                  >
                    Оставить отзыв <Star size={16} />
                  </button>
                )
              )}
            </div>
          )}
          {isStudent && ['confirmed', 'completed'].includes(b.status) && (
            <details className="payment-note">
              <summary>
                Показать демо-расчёт <ChevronRight size={14} />
              </summary>
              <p>Деньги не списываются. Это только модель стоимости встречи и комиссии.</p>
              {b.receipt ? (
                <p className="receipt-info">
                  Чек {b.receipt.id}
                  <br />
                  Стоимость: {money(b.receipt.amount)}
                  <br />
                  Комиссия: {money(b.receipt.commission)}
                  <br />
                  Ментору: {money(b.receipt.mentor_amount)}
                  <br />
                  <strong>Списано: 0 ₸</strong>
                </p>
              ) : (
                <button
                  className="button button-outline full"
                  disabled={working}
                  onClick={async () => {
                    setError('');
                    try {
                      await mutate('/bookings/' + id + '/payment-simulation', {});
                      await load();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Смоделировать оплату
                </button>
              )}
            </details>
          )}
          {active(b) && (
            <button
              className="cancel-link"
              disabled={working}
              onClick={() => void action('cancel')}
            >
              Отменить запись
            </button>
          )}
        </aside>
      </div>
      {reviewOpen && (
        <Modal title="Как вам объясняли?" close={() => setReviewOpen(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setError('');
              try {
                await mutate('/bookings/' + id + '/review', { rating, comment });
                await load();
                setReviewOpen(false);
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <div className="star-picker">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  type="button"
                  key={n}
                  className={n <= rating ? 'selected' : ''}
                  aria-label={`${n} из 5`}
                  aria-pressed={n === rating}
                  onClick={() => setRating(n)}
                >
                  <Star size={29} />
                </button>
              ))}
            </div>
            <label className="field">
              Что помогло разобраться?
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                minLength={3}
                maxLength={1000}
                required
                rows={4}
              />
            </label>
            <ErrorText message={error} />
            <button className="button button-primary full" disabled={working}>
              Сохранить отзыв <Check size={17} />
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
