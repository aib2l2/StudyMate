import { ArrowUpRight, Trophy } from 'lucide-react';
import { plural, topicsOf } from '../api';
import type { Snapshot } from '../types';

export function ProgressPage({
  data,
  practice,
}: {
  data: Snapshot;
  practice: (id: number) => void;
}) {
  return (
    <div className="content-page progress-page">
      <div className="page-heading">
        <span className="section-index">ЗАЧЁТКА / МАЛЕНЬКИЕ ПОБЕДЫ</span>
        <h1>
          Стало
          <br />
          <em>понятнее.</em>
        </h1>
        <p>Каждая встреча и самостоятельная попытка оставляют след.</p>
      </div>
      <div className="progress-total">
        <strong>
          {data.progress.points}
          <span>XP</span>
        </strong>
        <p>
          {data.progress.completed_sessions}{' '}
          {plural(data.progress.completed_sessions, [
            'встреча завершена',
            'встречи завершены',
            'встреч завершено',
          ])}
          <br />
          {data.progress.successful_tests}{' '}
          {plural(data.progress.successful_tests, ['тест', 'теста', 'тестов'])} с результатом 2–3 из
          3
        </p>
        <span className="progress-asterisk">✳</span>
      </div>
      <div className="subject-progress-list">
        {data.progress.plants.map((p, i) => (
          <article key={p.subject_id}>
            <span className="mono">0{i + 1}</span>
            <div>
              <h2>{p.name}</h2>
              <p>
                {p.points} XP ·{' '}
                {p.next_level
                  ? `ещё ${p.next_level - p.points} XP до следующего этапа`
                  : 'Весь маршрут отмечен'}
              </p>
              <div
                className="progress-track"
                role="progressbar"
                aria-label={'Прогресс: ' + p.name}
                aria-valuemin={0}
                aria-valuemax={120}
                aria-valuenow={Math.min(120, p.points)}
              >
                <span style={{ width: Math.min(100, (p.points / 120) * 100) + '%' }} />
              </div>
            </div>
            <span className={'skill-stamp stamp-level-' + p.level}>
              {['НАЧАЛО', 'ПЕРВЫЙ ШАГ', 'РАСТЁМ', 'ЕСТЬ ПРОГРЕСС'][p.level]}
            </span>
          </article>
        ))}
      </div>
      <div className="progress-columns">
        <section>
          <span className="section-index">ЕЩЁ ДВЕ МИНУТЫ?</span>
          <h2>Проверь конкретную тему.</h2>
          <div className="practice-topics">
            {topicsOf(data.catalog).map((t) => (
              <button key={t.id} onClick={() => practice(t.id)}>
                <span>{t.name}</span>
                <ArrowUpRight size={17} />
              </button>
            ))}
          </div>
        </section>
        <section>
          <span className="section-index">УЖЕ В ТВОЕЙ КОЛЛЕКЦИИ</span>
          <div className="achievement-stamps">
            {data.progress.achievements.map((a) => (
              <article key={a.name} className={a.earned ? 'earned' : ''}>
                <Trophy size={19} />
                <strong>{a.name}</strong>
                <p>{a.description}</p>
                <span>{a.earned ? 'ПОЛУЧЕНО ✓' : 'ЕЩЁ ВПЕРЕДИ'}</span>
              </article>
            ))}
          </div>
        </section>
      </div>
      <p className="micro progress-method">
        20 XP за первый успешный тест каждого этапа темы. 30 XP за подтверждённое завершение
        встречи. Баллы отмечают действия, а не гарантируют готовность к экзамену.
      </p>
    </div>
  );
}
