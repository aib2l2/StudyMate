import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { MouseEvent } from 'react';
import type { Navigate } from '../types';
import { ErrorText } from '../ui';

export type AuthMode = 'login' | 'register' | 'reset';

const TITLES: Record<AuthMode, [string, string]> = {
  login: ['РАДЫ СНОВА ВИДЕТЬ', 'Войти в StudyMate'],
  register: ['НАЧНЁМ ЗНАКОМСТВО', 'Присоединиться'],
  reset: ['ВОССТАНОВЛЕНИЕ ДОСТУПА', 'Новый пароль по коду'],
};

export function AuthPage({
  mode,
  query,
  navigate,
  working,
  authenticate,
  demo,
}: {
  mode: AuthMode;
  query: string;
  navigate: Navigate;
  working: boolean;
  authenticate: (path: string, body: unknown) => Promise<void>;
  demo?: () => void;
}) {
  const [email, setEmail] = useState(''),
    [password, setPassword] = useState(''),
    [name, setName] = useState(''),
    [course, setCourse] = useState(1),
    [code, setCode] = useState(''),
    [error, setError] = useState('');
  useEffect(() => setError(''), [mode]);
  const register = mode === 'register',
    reset = mode === 'reset';
  const errorId = error ? 'auth-error' : undefined;
  const go = (path: string) => (e: MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };
  return (
    <div className="auth-page">
      <section className="auth-editorial">
        <span className="section-index">ТВОЙ КАМПУС. ТВОЯ ПОДДЕРЖКА.</span>
        <h1>
          Спрашивать —<br />
          <em>нормально.</em>
        </h1>
        <div className="auth-symbol">✳</div>
        <p>
          У каждого есть тема, которую он знает хорошо.
          <br />И тема, с которой нужна помощь.
        </p>
      </section>
      <section className="auth-form">
        <span className="mono">{TITLES[mode][0]}</span>
        <h2>{TITLES[mode][1]}</h2>
        {reset && (
          <p className="muted">
            Владелец сайта выдаёт одноразовый код командой{' '}
            <code>python -m studymate reset-password --email …</code>. Код действует 30 минут.
          </p>
        )}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setError('');
            try {
              if (reset) await authenticate('/auth/reset', { email, code, new_password: password });
              else
                await authenticate(
                  register ? '/auth/register' : '/auth/login',
                  register ? { email, password, name, course } : { email, password },
                );
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          {register && (
            <>
              <label className="field">
                Как тебя зовут?
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={100}
                  autoComplete="given-name"
                  aria-describedby={errorId}
                  required
                />
              </label>
              <label className="field">
                На каком ты курсе?
                <select value={course} onChange={(e) => setCourse(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5, 6].map((n) => (
                    <option key={n} value={n}>
                      {n} курс
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          <label className="field">
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              maxLength={254}
              aria-invalid={Boolean(error)}
              aria-describedby={errorId}
              required
            />
          </label>
          {reset && (
            <label className="field">
              Код от владельца сайта
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                autoComplete="one-time-code"
                placeholder="XXXX-XXXX-XXXX"
                minLength={6}
                maxLength={32}
                aria-invalid={Boolean(error)}
                aria-describedby={errorId}
                required
              />
            </label>
          )}
          <label className="field">
            {reset ? 'Новый пароль' : 'Пароль'}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={10}
              maxLength={128}
              aria-invalid={Boolean(error)}
              aria-describedby={[errorId, mode !== 'login' ? 'password-hint' : '']
                .filter(Boolean)
                .join(' ')}
              required
            />
            {mode !== 'login' && <small id="password-hint">Минимум 10 символов.</small>}
          </label>
          <ErrorText message={error} id="auth-error" />
          <button className="button button-dark full" disabled={working}>
            {working
              ? 'Один момент…'
              : register
                ? 'Создать аккаунт'
                : reset
                  ? 'Сохранить и войти'
                  : 'Войти'}
            <ArrowRight size={17} />
          </button>
        </form>
        {mode === 'login' && (
          <p className="auth-switch">
            <a href="/reset" onClick={go('/reset' + query)}>
              Забыли пароль?
            </a>
          </p>
        )}
        <p className="auth-switch">
          {register ? 'Уже есть аккаунт?' : reset ? 'Вспомнили пароль?' : 'Первый раз здесь?'}{' '}
          <a
            href={(register || reset ? '/login' : '/register') + query}
            onClick={go((register || reset ? '/login' : '/register') + query)}
          >
            {register || reset ? 'Войти' : 'Зарегистрироваться'}
          </a>
        </p>
        {demo && !reset && (
          <div className="auth-demo">
            <span className="mono">ПРОСТО ПОСМОТРЕТЬ ПРОЕКТ?</span>
            <button className="inline-link" onClick={demo}>
              Открыть учебный аккаунт <ArrowUpRight size={17} />
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
