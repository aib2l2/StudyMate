import { ChevronDown } from 'lucide-react';
import { dateInput, languages, parseInput } from '../api';
import type { Filters, Subject } from '../types';

export function SearchFields({
  catalog,
  filters,
  onChange,
  compact = false,
  allowAnyTopic = false,
}: {
  catalog: Subject[];
  filters: Filters;
  onChange: (value: Filters) => void;
  compact?: boolean;
  /** Catalog only: "any topic" lets free-text search look across all subjects. */
  allowAnyTopic?: boolean;
}) {
  const field = (key: keyof Filters, value: string | number) =>
    onChange({ ...filters, [key]: value });
  return (
    <>
      <label className="field">
        Тема, с которой нужна помощь
        <select
          aria-label="Тема"
          value={filters.topic_id}
          onChange={(e) => field('topic_id', Number(e.target.value))}
        >
          {allowAnyTopic && <option value={0}>Любая тема</option>}
          {catalog
            .filter((s) => s.active)
            .map((s) => (
              <optgroup label={s.name} key={s.id}>
                {s.topics.map((t) => (
                  <option value={t.id} key={t.id}>
                    {t.name}
                  </option>
                ))}
              </optgroup>
            ))}
        </select>
      </label>
      <div className="form-pair">
        <label className="field">
          Бюджет за 30 мин, ₸
          <input
            aria-label="Бюджет"
            type="number"
            min={0}
            max={100000}
            step={100}
            value={filters.budget}
            onChange={(e) => field('budget', Number(e.target.value))}
            required
          />
        </label>
        <label className="field">
          Формат
          <select value={filters.format} onChange={(e) => field('format', e.target.value)}>
            <option value="online">Онлайн</option>
            <option value="campus">На кампусе</option>
          </select>
        </label>
      </div>
      <details className="search-details" open={!compact}>
        <summary>
          Время и язык <ChevronDown size={15} />
        </summary>
        <div className="detail-fields">
          <label className="field">
            Мне удобно после · Алматы
            <input
              type="datetime-local"
              value={dateInput(filters.earliest)}
              onChange={(e) => e.target.value && field('earliest', parseInput(e.target.value))}
              required
            />
          </label>
          <label className="field">
            Нужно успеть до · Алматы
            <input
              type="datetime-local"
              value={dateInput(filters.deadline)}
              min={dateInput(filters.earliest)}
              onChange={(e) => e.target.value && field('deadline', parseInput(e.target.value))}
              required
            />
          </label>
          <label className="field">
            Язык объяснения
            <select value={filters.language} onChange={(e) => field('language', e.target.value)}>
              {Object.entries(languages).map(([code, name]) => (
                <option key={code} value={code}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </details>
    </>
  );
}
