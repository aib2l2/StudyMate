import { ArrowRight, ArrowUpRight, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api, apiQueryOf, parseFilters, plural, queryOf, topicsOf } from '../api';
import { MentorRow } from '../components/MentorRow';
import { SearchFields } from '../components/SearchFields';
import type { Mentor, Navigate, Subject, ToggleFavorite } from '../types';
import { Busy, Empty, ErrorText } from '../ui';

export function CatalogPage({
  catalog,
  query,
  navigate,
  userId,
  favoriteIds,
  toggleFavorite,
}: {
  catalog: Subject[];
  query: string;
  navigate: Navigate;
  userId?: number;
  favoriteIds: Set<number>;
  toggleFavorite: ToggleFavorite;
}) {
  const signature = topicsOf(catalog)
    .map((t) => t.id)
    .join(',');
  const applied = useMemo(() => parseFilters(query, catalog), [query, signature]);
  const appliedKey = queryOf(applied);
  const apiKey = apiQueryOf(applied);
  const [draft, setDraft] = useState(applied),
    [rows, setRows] = useState<Mentor[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState('');
  useEffect(() => {
    setDraft(applied);
  }, [appliedKey]);
  const [searchRevision, setSearchRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError('');
    setRows([]);
    api<Mentor[]>((userId ? '/mentors?' : '/public/mentors?') + apiKey)
      .then((r) => {
        if (alive) setRows(r);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [apiKey, userId, searchRevision]);
  const dirty = queryOf(draft) !== appliedKey;
  const [waitError, setWaitError] = useState(''),
    [waitSuccess, setWaitSuccess] = useState(false);
  async function waitlist() {
    setWaitError('');
    if (!userId) {
      navigate('/login?next=' + encodeURIComponent('/mentors?' + appliedKey));
      return;
    }
    try {
      await api('/waitlist', { method: 'POST', body: JSON.stringify(applied) });
      setWaitSuccess(true);
    } catch (e) {
      setWaitError((e as Error).message);
    }
  }
  return (
    <div className="content-page catalog-page">
      <div className="page-heading">
        <span className="section-index">ЛЮДИ / ТЕМЫ / ВРЕМЯ</span>
        <h1>
          Найди своего
          <br />
          <em>человека.</em>
        </h1>
        <p>Не обязательно понимать с первого раза. Важно, чтобы было у кого спросить.</p>
      </div>
      <div className="catalog-layout">
        <aside>
          <form
            className="catalog-filter"
            onSubmit={(e) => {
              e.preventDefault();
              setWaitSuccess(false);
              setSearchRevision((v) => v + 1);
              navigate('/mentors?' + queryOf(draft));
            }}
          >
            <div className="filter-title">
              <Search size={18} />
              <span>Условия поиска</span>
            </div>
            <label className="field">
              Имя, тема или слово из анкеты
              <input
                type="search"
                value={draft.q}
                maxLength={200}
                placeholder="Например: JOIN, Аяулым, лабораторные"
                onChange={(e) => setDraft({ ...draft, q: e.target.value })}
              />
            </label>
            <SearchFields catalog={catalog} filters={draft} onChange={setDraft} allowAnyTopic />
            <label className="field">
              Сначала показывать
              <select
                value={draft.sort}
                onChange={(e) => setDraft({ ...draft, sort: e.target.value as typeof draft.sort })}
              >
                <option value="soonest">Ближайшее время</option>
                <option value="price">Ниже цена</option>
                <option value="rating">Выше рейтинг</option>
              </select>
            </label>
            {userId && (
              <label className="check-option">
                <input
                  type="checkbox"
                  checked={Boolean(draft.favorites_only)}
                  onChange={(e) => setDraft({ ...draft, favorites_only: e.target.checked ? 1 : 0 })}
                />
                Только избранные
              </label>
            )}
            <button className="button button-dark full" disabled={loading && !dirty}>
              Обновить поиск <ArrowRight size={16} />
            </button>
            {dirty && (
              <p className="filter-warning" role="status">
                Условия изменились. Обнови поиск, чтобы выбрать ментора.
              </p>
            )}
          </form>
        </aside>
        <section className="catalog-results">
          <div className="results-heading">
            <span className="mono">
              {loading
                ? 'СМОТРИМ РАСПИСАНИЕ'
                : `${rows.length} ${plural(rows.length, ['МЕНТОР', 'МЕНТОРА', 'МЕНТОРОВ'])} ПО УСЛОВИЯМ`}
            </span>
            <span>
              {applied.sort === 'price'
                ? 'Сначала ниже цена'
                : applied.sort === 'rating'
                  ? 'Сначала выше рейтинг (с учётом числа отзывов)'
                  : 'Ближайшее время сначала'}
            </span>
          </div>
          <ErrorText message={error} />
          {loading ? (
            <Busy />
          ) : rows.length ? (
            <div className={dirty ? 'results-list results-stale' : 'results-list'}>
              {rows.map((m, i) => (
                <MentorRow
                  key={m.id}
                  mentor={m}
                  index={i}
                  disabled={dirty}
                  open={() => navigate('/mentors/' + m.id + '?' + appliedKey)}
                  favorite={
                    userId
                      ? {
                          active: favoriteIds.has(m.id),
                          toggle: (on) => toggleFavorite(m.id, on),
                        }
                      : undefined
                  }
                />
              ))}
            </div>
          ) : (
            !error && (
              <Empty
                title="Пока не совпало"
                text="Попробуй другой язык, бюджет или более поздний дедлайн. Можно оставить запрос команде."
              >
                {waitSuccess ? (
                  <p className="success-note">
                    Запрос сохранён. Команда увидит его в листе ожидания.
                  </p>
                ) : (
                  <button
                    className="button button-primary"
                    disabled={!applied.topic_id}
                    title={applied.topic_id ? undefined : 'Для запроса выберите конкретную тему'}
                    onClick={() => void waitlist()}
                  >
                    Оставить запрос <ArrowUpRight size={17} />
                  </button>
                )}
                <ErrorText message={waitError} />
              </Empty>
            )
          )}
        </section>
      </div>
    </div>
  );
}
