import { Download, KeyRound, LogOut } from 'lucide-react';
import { useState } from 'react';
import { api, send, SessionChanged } from '../api';
import type { User } from '../types';
import { ErrorText } from '../ui';

/** Password change, "sign out everywhere" and personal data export. */
export function SecurityPanel({
  user,
  signedOut,
}: {
  user: User;
  /** Called after the server revoked every session of this account. */
  signedOut: () => void;
}) {
  const [current, setCurrent] = useState(''),
    [next, setNext] = useState(''),
    [repeat, setRepeat] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [done, setDone] = useState('');
  const mismatch = repeat.length > 0 && next !== repeat;

  async function run(action: () => Promise<string | void>) {
    setBusy(true);
    setError('');
    setDone('');
    try {
      const message = await action();
      if (message) setDone(message);
    } catch (e) {
      if (!(e instanceof SessionChanged)) setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function exportData() {
    const data = await api<unknown>('/me/export');
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `studymate-${user.id}-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    return 'Файл с вашими данными сохранён.';
  }

  return (
    <div className="security-panel">
      <ErrorText message={error} id="security-error" />
      {done && (
        <p className="success-note" role="status">
          {done}
        </p>
      )}
      {user.email ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              const result = await send<{ message: string }>('/auth/password', {
                current_password: current,
                new_password: next,
              });
              setCurrent('');
              setNext('');
              setRepeat('');
              return result.message;
            });
          }}
        >
          <h2>Сменить пароль</h2>
          <label className="field">
            Текущий пароль
            <input
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              autoComplete="current-password"
              maxLength={128}
              aria-describedby={error ? 'security-error' : undefined}
              required
            />
          </label>
          <label className="field">
            Новый пароль
            <input
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              autoComplete="new-password"
              minLength={10}
              maxLength={128}
              aria-describedby="new-password-hint"
              required
            />
            <small id="new-password-hint">Минимум 10 символов. Другие устройства выйдут.</small>
          </label>
          <label className="field">
            Повторите новый пароль
            <input
              type="password"
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
              autoComplete="new-password"
              maxLength={128}
              aria-invalid={mismatch}
              aria-describedby={mismatch ? 'repeat-error' : undefined}
              required
            />
            {mismatch && (
              <small className="field-error" id="repeat-error">
                Пароли не совпадают.
              </small>
            )}
          </label>
          <button className="button button-dark" disabled={busy || mismatch || !next}>
            Сменить пароль <KeyRound size={17} />
          </button>
        </form>
      ) : (
        <p className="muted">
          У учебного аккаунта защиты нет пароля. Смена пароля доступна аккаунтам с email.
        </p>
      )}
      <hr />
      <h2>Сессии</h2>
      <p className="muted">Завершает вход на всех устройствах и в этом браузере тоже.</p>
      <button
        className="button"
        disabled={busy}
        onClick={() =>
          void run(async () => {
            await send('/auth/logout-all', {});
            signedOut();
          })
        }
      >
        Выйти на всех устройствах <LogOut size={17} />
      </button>
      <hr />
      <h2>Мои данные</h2>
      <p className="muted">
        JSON-файл: профиль, встречи, ваши личные заметки, попытки тестов и прогресс. Чужие заметки в
        него не попадают.
      </p>
      <button className="button" disabled={busy} onClick={() => void run(exportData)}>
        Скачать мои данные <Download size={17} />
      </button>
    </div>
  );
}
