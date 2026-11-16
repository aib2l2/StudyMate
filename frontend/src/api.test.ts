import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  api,
  apiQueryOf,
  defaultFilters,
  parseFilters,
  plural,
  queryOf,
  SessionChanged,
  setToken,
} from './api';
import type { Subject } from './types';

const catalog: Subject[] = [
  {
    id: 1,
    slug: 'db',
    name: 'Базы данных',
    active: true,
    topics: [{ id: 1, name: 'SQL JOIN', code: 'sql_join' }],
  },
  {
    id: 2,
    slug: 'py',
    name: 'Python',
    active: true,
    topics: [{ id: 4, name: 'Циклы', code: 'loops' }],
  },
  {
    id: 3,
    slug: 'off',
    name: 'Отключён',
    active: false,
    topics: [{ id: 9, name: 'X', code: 'x' }],
  },
];

afterEach(() => {
  vi.unstubAllGlobals();
  setToken('');
});

describe('filters in the URL', () => {
  it('round-trips through queryOf/parseFilters', () => {
    const filters = { ...defaultFilters(catalog), topic_id: 4, budget: 1500, language: 'en' };
    expect(parseFilters(queryOf(filters), catalog)).toEqual(filters);
  });

  it('keeps an explicit "any topic" choice', () => {
    expect(parseFilters('topic_id=0&q=спокойн', catalog).topic_id).toBe(0);
  });

  it('falls back to the first active topic for unknown or disabled topics', () => {
    expect(parseFilters('topic_id=9', catalog).topic_id).toBe(1);
    expect(parseFilters('topic_id=abc&budget=NaN', catalog).budget).toBe(3000);
  });
});

describe('search filters in the URL', () => {
  it('keeps text, sort and favorites, and omits defaults', () => {
    const base = defaultFilters(catalog);
    expect(queryOf(base)).not.toMatch(/q=|sort=|favorites_only=/);
    const filters = { ...base, q: 'LEFT JOIN', sort: 'rating' as const, favorites_only: 1 };
    const query = queryOf(filters);
    expect(query).toContain('q=LEFT+JOIN');
    expect(parseFilters(query, catalog)).toEqual(filters);
    expect(apiQueryOf(filters)).toContain('favorites_only=true');
    expect(parseFilters('sort=evil&favorites_only=yes', catalog)).toMatchObject({
      sort: 'soonest',
      favorites_only: 0,
    });
  });
});

describe('plural', () => {
  it('uses Russian plural forms', () => {
    const forms: [string, string, string] = ['ментор', 'ментора', 'менторов'];
    expect([1, 2, 5, 11, 21, 22, 112].map((n) => plural(n, forms))).toEqual([
      'ментор',
      'ментора',
      'менторов',
      'менторов',
      'ментор',
      'ментора',
      'менторов',
    ]);
  });
});

describe('api()', () => {
  it('sends the bearer token and returns JSON', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    setToken('secret-token');
    await expect(api('/me')).resolves.toEqual({ ok: true });
    expect(fetch.mock.calls[0][0]).toBe('/api/me');
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer secret-token');
  });

  it('shows the server message for a failed request', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('{"detail":"Это время уже занято"}', { status: 409 })),
    );
    await expect(api('/bookings')).rejects.toThrow('Это время уже занято');
  });

  it('drops responses that belong to a previous account', async () => {
    let resolve: (r: Response) => void = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((r) => (resolve = r))),
    );
    setToken('first-account');
    const pending = api('/bookings');
    setToken('second-account');
    resolve(new Response('[]', { status: 200 }));
    await expect(pending).rejects.toBeInstanceOf(SessionChanged);
  });

  it('announces an expired session on 401 outside /auth', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })));
    const listener = vi.fn();
    window.addEventListener('studymate:expired', listener);
    await expect(api('/me')).rejects.toBeInstanceOf(SessionChanged);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener('studymate:expired', listener);
  });
});
