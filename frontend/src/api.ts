let token = (() => {
  try {
    return sessionStorage.getItem('studymate-token') || '';
  } catch {
    return '';
  }
})();
let generation = 0;
let controller = new AbortController();
export class SessionChanged extends Error {}
export const setToken = (value: string) => {
  generation++;
  controller.abort();
  controller = new AbortController();
  token = value;
  try {
    if (value) sessionStorage.setItem('studymate-token', value);
    else sessionStorage.removeItem('studymate-token');
  } catch {
    // Storage can be unavailable (private mode); the in-memory token still works.
  }
};
export const hasToken = () => Boolean(token);
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const epoch = generation;
  let response: Response;
  try {
    response = await fetch('/api' + path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
        ...options.headers,
      },
      signal: AbortSignal.any([
        controller.signal,
        AbortSignal.timeout(20000),
        ...(options.signal ? [options.signal] : []),
      ]),
    });
  } catch {
    if (epoch !== generation) throw new SessionChanged();
    throw new Error(
      'Не удалось связаться с сайтом. Проверьте, что StudyMate запущен, и повторите действие.',
    );
  }
  if (epoch !== generation) throw new SessionChanged();
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Не удалось выполнить действие' }));
    if (response.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new Event('studymate:expired'));
      throw new SessionChanged();
    }
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Проверьте заполнение полей');
  }
  return response.json() as Promise<T>;
}
/** Download a protected file (e.g. .ics) with the session header, via a Blob. */
export async function download(path: string, filename: string) {
  const response = await fetch('/api' + path, {
    headers: token ? { Authorization: 'Bearer ' + token } : {},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Файл недоступен' }));
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Файл недоступен');
  }
  const link = document.createElement('a');
  link.href = URL.createObjectURL(await response.blob());
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
export const send = <T>(path: string, body: unknown, method = 'POST') =>
  api<T>(path, { method, body: JSON.stringify(body) });
export const money = (value: number) => new Intl.NumberFormat('ru-RU').format(value) + ' ₸';
export const dateTime = (value: number) =>
  new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Asia/Almaty',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(value * 1000);
export const dateOnly = (value: number) =>
  new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Asia/Almaty',
    day: 'numeric',
    month: 'long',
  }).format(value * 1000);
export const shortTime = (value: number) =>
  new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Asia/Almaty',
    hour: '2-digit',
    minute: '2-digit',
  }).format(value * 1000);
export const dateInput = (value: number) =>
  new Date(value * 1000 + 5 * 3600000).toISOString().slice(0, 16);
export const parseInput = (value: string) => Math.floor(Date.parse(value + ':00+05:00') / 1000);
export const clock = () => Math.floor(Date.now() / 1000);
export const languages: Record<string, string> = { ru: 'Русский', en: 'English', kk: 'Қазақша' };
export const topicsOf = (catalog: import('./types').Subject[]) =>
  catalog
    .filter((s) => s.active)
    .flatMap((s) => s.topics.map((t) => ({ ...t, subject_id: s.id, subject: s.name })));
export const defaultFilters = (
  catalog: import('./types').Subject[],
): import('./types').Filters => ({
  topic_id: topicsOf(catalog)[0]?.id || 0,
  budget: 3000,
  earliest: clock() + 120,
  deadline: clock() + 86400,
  language: 'ru',
  format: 'online',
  q: '',
  sort: 'soonest',
  favorites_only: 0,
});
export function parseFilters(query: string, catalog: import('./types').Subject[]) {
  const params = new URLSearchParams(query),
    base = defaultFilters(catalog);
  for (const k of ['topic_id', 'budget', 'earliest', 'deadline'] as const) {
    const v = params.get(k);
    if (v && Number.isFinite(Number(v))) base[k] = Number(v);
  }
  // topic_id=0 explicitly means "any topic" (catalog search across subjects).
  const anyTopic = params.get('topic_id') === '0';
  if (!anyTopic && !topicsOf(catalog).some((t) => t.id === base.topic_id))
    base.topic_id = topicsOf(catalog)[0]?.id || 0;
  for (const k of ['language', 'format'] as const) {
    const v = params.get(k);
    if (v) base[k] = v;
  }
  base.q = (params.get('q') || '').slice(0, 200);
  const sort = params.get('sort');
  if (sort === 'price' || sort === 'rating') base.sort = sort;
  base.favorites_only = params.get('favorites_only') === '1' ? 1 : 0;
  return base;
}
/** URL form of filters; defaults of the optional search fields are left out. */
export const queryOf = (filters: import('./types').Filters) =>
  new URLSearchParams(
    Object.entries(filters)
      .filter(([k, v]) => !(k === 'q' && !v) && !(k === 'sort' && v === 'soonest'))
      .filter(([k, v]) => !(k === 'favorites_only' && !v))
      .map(([k, v]) => [k, String(v)]),
  ).toString();

/** Query for the mentors API: the URL flag 1/0 becomes true/false. */
export const apiQueryOf = (filters: import('./types').Filters) =>
  queryOf(filters).replace('favorites_only=1', 'favorites_only=true');
export const plural = (count: number, forms: [string, string, string]) => {
  const n = Math.abs(count) % 100,
    d = n % 10;
  return n >= 11 && n <= 14
    ? forms[2]
    : d === 1
      ? forms[0]
      : d >= 2 && d <= 4
        ? forms[1]
        : forms[2];
};
