import { ArrowUpRight, Check, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { languages, topicsOf } from '../api';
import { SecurityPanel } from '../components/SecurityPanel';
import type { Mutate, Snapshot } from '../types';
import { Avatar, Badge, ErrorText } from '../ui';

export function AccountPage({
  data,
  mutate,
  working,
  logout,
  signedOut,
}: {
  data: Snapshot;
  mutate: Mutate;
  working: boolean;
  logout: () => void;
  signedOut: () => void;
}) {
  const u = data.user,
    m = u.mentor;
  const [tab, setTab] = useState('profile'),
    [name, setName] = useState(u.name),
    [course, setCourse] = useState(u.course),
    [langs, setLangs] = useState(u.languages),
    [interests, setInterests] = useState(u.interests),
    [bio, setBio] = useState(m?.bio || ''),
    [price, setPrice] = useState(m?.price ?? 2500),
    [topicIds, setTopicIds] = useState(m?.topic_ids || []),
    [formats, setFormats] = useState(m?.formats || ['online']),
    [accepting, setAccepting] = useState(m?.active ?? true),
    [error, setError] = useState(''),
    [saved, setSaved] = useState('');
  const toggle = <T,>(array: T[], value: T) =>
    array.includes(value) ? array.filter((v) => v !== value) : [...array, value];
  async function save(path: string, body: unknown) {
    setError('');
    setSaved('');
    try {
      await mutate(path, body, 'PUT');
      setSaved('Сохранено. Всё на месте.');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="content-page account-page">
      <div className="page-heading">
        <span className="section-index">ЛИЧНЫЙ КАБИНЕТ</span>
        <h1>
          Давай
          <br />
          <em>знакомиться.</em>
        </h1>
      </div>
      <div className="account-grid">
        <aside className="account-index">
          <Avatar name={u.name} id={u.id} large />
          <h2>{u.name}</h2>
          <p>
            {u.email || 'Учебный аккаунт для защиты'}
            <br />
            Astana IT University
          </p>
          <button
            aria-pressed={tab === 'profile'}
            onClick={() => {
              setTab('profile');
              setError('');
              setSaved('');
            }}
          >
            01 / Мой профиль
          </button>
          <button
            aria-pressed={tab === 'mentor'}
            onClick={() => {
              setTab('mentor');
              setError('');
              setSaved('');
            }}
          >
            02 / Анкета ментора
          </button>
          <button
            aria-pressed={tab === 'security'}
            onClick={() => {
              setTab('security');
              setError('');
              setSaved('');
            }}
          >
            03 / Безопасность и данные
          </button>
          <button className="logout-button" onClick={logout}>
            Выйти из аккаунта ↗
          </button>
        </aside>
        <section className="account-form">
          <ErrorText message={error} />
          {saved && (
            <p className="success-note" role="status">
              {saved}
            </p>
          )}
          {tab === 'security' ? (
            <SecurityPanel user={u} signedOut={signedOut} />
          ) : tab === 'profile' ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void save('/me', { name, course, languages: langs, interests });
              }}
            >
              <h2>Немного о тебе</h2>
              <label className="field">
                Имя
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={100}
                  required
                />
              </label>
              <label className="field">
                Курс
                <select value={course} onChange={(e) => setCourse(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5, 6].map((n) => (
                    <option key={n} value={n}>
                      {n} курс
                    </option>
                  ))}
                </select>
              </label>
              <fieldset className="checkbox-set">
                <legend>Языки общения</legend>
                {Object.entries(languages).map(([code, label]) => (
                  <label key={code}>
                    <input
                      type="checkbox"
                      checked={langs.includes(code)}
                      onChange={() => setLangs(toggle(langs, code))}
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
              <fieldset className="checkbox-set">
                <legend>Интересные предметы</legend>
                {data.catalog
                  .filter((s) => s.active)
                  .map((s) => (
                    <label key={s.id}>
                      <input
                        type="checkbox"
                        checked={interests.includes(s.id)}
                        onChange={() => setInterests(toggle(interests, s.id))}
                      />
                      {s.name}
                    </label>
                  ))}
              </fieldset>
              <button className="button button-dark" disabled={working || !langs.length}>
                Сохранить профиль <Check size={17} />
              </button>
            </form>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void save('/mentor/profile', {
                  bio,
                  price,
                  topic_ids: topicIds,
                  formats,
                  active: accepting,
                });
              }}
            >
              <h2>{m ? 'Твоя анкета ментора' : 'Поделись тем, что знаешь'}</h2>
              <p className="muted">Можно учиться и объяснять свои сильные темы в одном аккаунте.</p>
              {m?.suspended && (
                <p className="field-error">
                  Команда приостановила анкету. Настройка доступности не снимает это ограничение.
                </p>
              )}
              {m?.verified && (
                <Badge tone="blue">
                  <ShieldCheck size={14} />
                  Проверен командой
                </Badge>
              )}
              <label className="field">
                Как ты помогаешь?
                <textarea
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  minLength={15}
                  maxLength={1000}
                  rows={4}
                  required
                  placeholder="Какие темы изучал? На каких примерах объясняешь?"
                />
              </label>
              <label className="field">
                Цена за 30 минут, ₸
                <input
                  type="number"
                  min={0}
                  max={100000}
                  step={100}
                  value={price}
                  onChange={(e) => setPrice(Number(e.target.value))}
                  required
                />
              </label>
              <fieldset className="checkbox-set">
                <legend>Твои сильные темы</legend>
                {topicsOf(data.catalog).map((t) => (
                  <label key={t.id}>
                    <input
                      type="checkbox"
                      checked={topicIds.includes(t.id)}
                      onChange={() => setTopicIds(toggle(topicIds, t.id))}
                    />
                    {t.name}
                  </label>
                ))}
              </fieldset>
              <fieldset className="checkbox-set">
                <legend>Формат</legend>
                {[
                  ['online', 'Онлайн'],
                  ['campus', 'На кампусе'],
                ].map(([code, label]) => (
                  <label key={code}>
                    <input
                      type="checkbox"
                      checked={formats.includes(code)}
                      onChange={() => setFormats(toggle(formats, code))}
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
              <label className="check-option">
                <input
                  type="checkbox"
                  checked={accepting}
                  onChange={(e) => setAccepting(e.target.checked)}
                />
                Я готов принимать новые заявки
              </label>
              <button
                className="button button-primary"
                disabled={working || !topicIds.length || !formats.length}
              >
                Сохранить анкету <ArrowUpRight size={17} />
              </button>
              <p className="micro">
                После изменения тем или описания отметку проверки нужно получить заново. Свободное
                время добавляется в календаре.
              </p>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
