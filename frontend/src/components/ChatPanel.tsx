import { RotateCcw, Send } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, send, SessionChanged, shortTime } from '../api';
import { onLive } from '../live';
import type { ChatMessage, ChatThread } from '../types';
import { ErrorText } from '../ui';

type Pending = { client_id: string; body: string; failed: boolean };

const newId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);

/** Lesson chat. Plain text only; new messages arrive through live hints. */
export function ChatPanel({ bookingId, userId }: { bookingId: string; userId: number }) {
  const [thread, setThread] = useState<ChatThread | null>(null),
    [draft, setDraft] = useState(''),
    [pending, setPending] = useState<Pending[]>([]),
    [error, setError] = useState(''),
    [announce, setAnnounce] = useState('');
  const known = useRef(new Set<number>());
  const listRef = useRef<HTMLOListElement>(null);

  const load = useCallback(async () => {
    try {
      const next = await api<ChatThread>(`/bookings/${bookingId}/messages`);
      const incoming = next.messages.filter(
        (m) => !known.current.has(m.id) && m.sender_id !== userId,
      );
      if (known.current.size && incoming.length) {
        const last = incoming[incoming.length - 1];
        setAnnounce(`Новое сообщение от ${last.sender_name}: ${last.body}`);
      }
      next.messages.forEach((m) => known.current.add(m.id));
      setThread(next);
      setError('');
      const lastId = next.messages.at(-1)?.id ?? 0;
      if (lastId > next.my_last_read_id && document.visibilityState === 'visible')
        await send(`/bookings/${bookingId}/messages/read`, { last_read_id: lastId });
    } catch (e) {
      if (!(e instanceof SessionChanged)) setError((e as Error).message);
    }
  }, [bookingId, userId]);

  useEffect(() => {
    known.current = new Set();
    void load();
    // Fallback when the live stream is unavailable.
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') void load();
    }, 15000);
    const stop = onLive((event) => {
      if (event.type === 'thread' && thread_matches(event.id, bookingId)) void load();
    });
    return () => {
      clearInterval(timer);
      stop();
    };
  }, [bookingId, load]);

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [thread?.messages.length, pending.length]);

  async function deliver(item: Pending) {
    try {
      await send<ChatMessage>(`/bookings/${bookingId}/messages`, {
        body: item.body,
        client_id: item.client_id,
      });
      setPending((all) => all.filter((p) => p.client_id !== item.client_id));
      await load();
    } catch (e) {
      if (e instanceof SessionChanged) return;
      setPending((all) =>
        all.map((p) => (p.client_id === item.client_id ? { ...p, failed: true } : p)),
      );
      setError((e as Error).message);
    }
  }

  function submit() {
    const body = draft.trim();
    if (!body) return;
    const item = { client_id: newId(), body, failed: false };
    setPending((all) => [...all, item]);
    setDraft('');
    void deliver(item);
  }

  const mine = thread?.messages.filter((m) => m.sender_id === userId) ?? [];
  const lastMine = mine.at(-1);
  return (
    <section className="lesson-section chat-panel" aria-labelledby="chat-title">
      <span className="mono">05 / ПЕРЕПИСКА</span>
      <h2 id="chat-title">Вопросы до и после встречи</h2>
      <p className="micro">Видна участникам занятия. Команда StudyMate её не читает.</p>
      <ol className="chat-list" ref={listRef} aria-label="Сообщения">
        {thread?.messages.map((m) => (
          <li key={m.id} className={m.sender_id === userId ? 'chat-own' : ''}>
            <span className="chat-meta">
              {m.sender_id === userId ? 'Вы' : m.sender_name} · {shortTime(m.created_at)}
            </span>
            <p className="preserve-lines">{m.body}</p>
            {lastMine?.id === m.id && thread.others_last_read_id >= m.id && (
              <span className="chat-read">Прочитано</span>
            )}
          </li>
        ))}
        {pending.map((p) => (
          <li key={p.client_id} className="chat-own chat-pending">
            <span className="chat-meta">{p.failed ? 'Не отправлено' : 'Отправляется…'}</span>
            <p className="preserve-lines">{p.body}</p>
            {p.failed && (
              <button
                type="button"
                className="inline-link"
                onClick={() => {
                  setPending((all) =>
                    all.map((x) => (x.client_id === p.client_id ? { ...x, failed: false } : x)),
                  );
                  void deliver({ ...p, failed: false });
                }}
              >
                Повторить <RotateCcw size={14} />
              </button>
            )}
          </li>
        ))}
        {thread && !thread.messages.length && !pending.length && (
          <li className="chat-empty">Сообщений пока нет. Можно уточнить вопрос заранее.</li>
        )}
      </ol>
      <p className="visually-hidden" aria-live="polite">
        {announce}
      </p>
      <ErrorText message={error} id="chat-error" />
      {thread?.can_write ? (
        <form
          className="chat-form"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <label className="field">
            Сообщение
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
              rows={2}
              maxLength={2000}
              aria-describedby={error ? 'chat-error chat-hint' : 'chat-hint'}
            />
            <small id="chat-hint">Enter — отправить, Shift+Enter — новая строка.</small>
          </label>
          <button className="button button-dark" disabled={!draft.trim()}>
            Отправить <Send size={16} />
          </button>
        </form>
      ) : (
        thread && <p className="muted">Переписка закрыта: её можно только читать.</p>
      )}
    </section>
  );
}

function thread_matches(id: string | undefined, bookingId: string) {
  // Group rooms use slot:{id}; the server re-checks access, so a reload is cheap and safe.
  return !id || id === `booking:${bookingId}` || id.startsWith('slot:');
}
