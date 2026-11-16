import { ArrowDown, ArrowUpRight, Clock3 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, defaultFilters, money, queryOf, topicsOf } from '../api';
import { SearchFields } from '../components/SearchFields';
import type { Mentor, Navigate, Subject, User } from '../types';
import { Avatar } from '../ui';

export function HomePage({
  catalog,
  navigate,
  user,
}: {
  catalog: Subject[];
  navigate: Navigate;
  user: User | null;
}) {
  const [filters, setFilters] = useState(() => defaultFilters(catalog)),
    [featured, setFeatured] = useState<Mentor[]>([]);
  const ids = topicsOf(catalog)
    .map((t) => t.id)
    .join(',');
  useEffect(() => {
    if (!topicsOf(catalog).some((t) => t.id === filters.topic_id))
      setFilters((f) => ({ ...f, topic_id: topicsOf(catalog)[0]?.id || 0 }));
  }, [ids, filters.topic_id]);
  useEffect(() => {
    let alive = true;
    api<Mentor[]>('/public/mentors?budget=3000')
      .then((rows) => {
        if (alive) setFeatured(rows.filter((m) => m.id !== user?.id).slice(0, 3));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [user?.id, ids]);
  return (
    <div className="home-page">
      <section className="editorial-hero">
        <div className="hero-copy">
          <span className="kicker">
            <span className="rust-dot" />
            ЗНАНИЯ УЖЕ ЕСТЬ В ТВОЁМ КАМПУСЕ
          </span>
          <h1>
            Разобраться
            <br />
            <em>вместе.</em>
            <span className="headline-star">✳</span>
          </h1>
          <p>
            Не понял тему? Найди старшекурсника,
            <br className="desktop-only" /> который уже через это прошёл.
          </p>
          <a
            className="inline-link"
            href="#find"
            onClick={(e) => {
              e.preventDefault();
              document.getElementById('find')?.scrollIntoView({ behavior: 'smooth' });
            }}
          >
            Найдём твоего человека <ArrowDown size={17} />
          </a>
          <div className="handwritten-note">
            Сложный вопрос —<br />
            хорошее начало.
          </div>
        </div>
        <div className="hero-art">
          <img
            src="/images/campus-editorial.png"
            alt="Студенты обсуждают задачу за общим столом — авторская иллюстрация StudyMate"
          />
          <span className="art-caption">ОБЪЯСНИТЬ. ПОПРОБОВАТЬ. ПОНЯТЬ.</span>
          <span className="paper-stamp">
            AI<span>TU</span>
          </span>
        </div>
      </section>
      <div className="editorial-ticker">
        <span>ТВОЯ ТЕМА</span>
        <i>✳</i>
        <span>ТВОЙ ТЕМП</span>
        <i>✳</i>
        <span>СВОИ ЛЮДИ</span>
        <i>✳</i>
        <span>БОЛЬШЕ ПОНИМАНИЯ</span>
        <i>✳</i>
      </div>
      <section className="find-section" id="find">
        <div className="find-intro">
          <span className="section-index">01 / НАЧНЁМ С ГЛАВНОГО</span>
          <h2>
            Что сегодня
            <br />
            <em>не сходится?</em>
          </h2>
          <p>
            JOIN, функции или подсети — выбери одну тему. Подберём людей по времени, языку и
            бюджету.
          </p>
          <div className="duration-note">
            <Clock3 size={23} />
            <span>
              <strong>30 минут на один вопрос.</strong>
              <small>Без долгих курсов и лишних обещаний.</small>
            </span>
          </div>
        </div>
        <form
          className="find-note"
          onSubmit={(e) => {
            e.preventDefault();
            navigate('/mentors?' + queryOf(filters));
          }}
        >
          <div className="note-top">
            <span className="mono">ЗАПРОС НА ПОМОЩЬ</span>
            <span>↗</span>
          </div>
          <SearchFields compact catalog={catalog} filters={filters} onChange={setFilters} />
          <button className="button button-primary full" disabled={!filters.topic_id}>
            Найти ментора <ArrowUpRight size={18} />
          </button>
          <p className="micro">Цена видна заранее. Запись подтверждает сам ментор.</p>
        </form>
      </section>
      <section className="people-section">
        <div className="section-title">
          <div>
            <span className="section-index">02 / ЛЮДИ РЯДОМ</span>
            <h2>
              На один курс старше.
              <br />
              <em>На одну тему ближе.</em>
            </h2>
          </div>
          <button className="inline-link" onClick={() => navigate('/mentors')}>
            Все менторы <ArrowUpRight size={19} />
          </button>
        </div>
        <div className="featured-people">
          {featured.map((m, i) => (
            <button
              className="featured-person"
              key={m.id}
              onClick={() => navigate('/mentors/' + m.id)}
            >
              <span className="mono person-number">0{i + 1}</span>
              <Avatar name={m.name} id={m.id} large />
              <h3>{m.name}</h3>
              <p>{m.course} курс / AITU</p>
              <div className="topic-line">
                {m.topics.slice(0, 2).map((t) => (
                  <span key={t.id}>{t.name}</span>
                ))}
              </div>
              <div className="person-bottom">
                <strong>
                  {money(m.price)} <small>/ 30 мин</small>
                </strong>
                <ArrowUpRight size={23} />
              </div>
            </button>
          ))}
        </div>
      </section>
      <section className="how-section" id="how">
        <span className="section-index">03 / БЕЗ СЛОЖНЫХ СХЕМ</span>
        <h2>
          Вопрос превращается
          <br />
          <em>в понятный следующий шаг.</em>
        </h2>
        <div className="how-grid">
          {[
            ['01', 'Выбери тему', 'Напиши, на каком шаге застрял, и выбери удобное время.'],
            [
              '02',
              'Договорись о встрече',
              'Ментор подтвердит запись и добавит ссылку на звонок или место на кампусе.',
            ],
            [
              '03',
              'Разберись и попробуй',
              'Сохрани материалы, сделай заметки и проверь понимание после встречи.',
            ],
          ].map(([n, title, text]) => (
            <article key={n}>
              <span>{n}</span>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="mentor-invite">
        <span className="invite-star">✳</span>
        <div>
          <span className="mono">ОБЪЯСНЯЕШЬ ДРУЗЬЯМ ПЕРЕД ЭКЗАМЕНОМ?</span>
          <h2>
            Кажется, ты уже <em>ментор.</em>
          </h2>
          <p>Добавь свои сильные темы и время. Остальное соберём в одном месте.</p>
        </div>
        <button
          className="button button-dark"
          onClick={() => navigate(user ? '/account' : '/register?next=%2Faccount')}
        >
          Попробовать <ArrowUpRight size={18} />
        </button>
      </section>
    </div>
  );
}
