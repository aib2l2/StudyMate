import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowUpRight,
  Bell,
  ChevronDown,
  LogOut,
  Menu,
  Moon,
  Sun,
  UserRound,
  X,
} from 'lucide-react';
import { api, hasToken, send, SessionChanged, setToken } from './api';
import { broadcast, useEventStream } from './live';
import type { Config, Mutate, Quiz, Snapshot, Subject, User } from './types';
import { Avatar, Busy, ErrorText, Logo, Modal } from './ui';
import { QuizDialog } from './components/QuizDialog';
import { AccountPage } from './pages/AccountPage';
import { AuthPage } from './pages/AuthPage';
import { CalendarPage } from './pages/CalendarPage';
import { CatalogPage } from './pages/CatalogPage';
import { DashboardPage } from './pages/DashboardPage';
import { HomePage } from './pages/HomePage';
import { LessonPage } from './pages/LessonPage';
import { MentorPage } from './pages/MentorPage';
import { ProgressPage } from './pages/ProgressPage';
import { TeamPage } from './pages/TeamPage';
export default function App() {
  const [route, setRoute] = useState(location.pathname + location.search),
    [config, setConfig] = useState<Config | null>(null),
    [catalog, setCatalog] = useState<Subject[]>([]),
    [data, setData] = useState<Snapshot | null>(null),
    [ready, setReady] = useState(false),
    [fatal, setFatal] = useState('');
  const [demoOpen, setDemoOpen] = useState(false),
    [demoError, setDemoError] = useState(''),
    [working, setWorking] = useState(false),
    [menu, setMenu] = useState(false),
    [userMenu, setUserMenu] = useState(false),
    [inboxOpen, setInboxOpen] = useState(false),
    [quiz, setQuiz] = useState<Quiz | null>(null),
    [toast, setToast] = useState(''),
    [offline, setOffline] = useState(false);
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem('studymate-theme') || 'light';
    } catch {
      return 'light';
    }
  });
  const revision = useRef(0),
    toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const path = route.split('?')[0],
    query = route.includes('?') ? '?' + route.split('?').slice(1).join('?') : '';
  const navigate = useCallback((next: string) => {
    if (location.pathname + location.search !== next) history.pushState({}, '', next);
    setRoute(next);
    setMenu(false);
    setUserMenu(false);
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, []);
  useEffect(() => {
    const back = () => {
      setRoute(location.pathname + location.search);
      setMenu(false);
    };
    window.addEventListener('popstate', back);
    return () => window.removeEventListener('popstate', back);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    try {
      localStorage.setItem('studymate-theme', theme);
    } catch {
      // Theme simply is not remembered when storage is blocked.
    }
  }, [theme]);
  const tell = useCallback((message: string) => {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(''), 4500);
  }, []);
  const refresh = useCallback(async () => {
    const current = ++revision.current;
    const subjects = await api<Subject[]>('/public/catalog');
    let snapshot: Snapshot | null = null;
    if (hasToken()) {
      const user = await api<User>('/me');
      const [bookings, progress, notifications, slots, waitlist, favorites, admin] =
        await Promise.all([
          api<Snapshot['bookings']>('/bookings'),
          api<Snapshot['progress']>('/progress'),
          api<Snapshot['notifications']>('/notifications'),
          api<Snapshot['slots']>('/mentor/slots'),
          api<Snapshot['waitlist']>('/waitlist'),
          api<Snapshot['favorites']>('/favorites'),
          user.is_admin ? api<Snapshot['admin']>('/admin') : Promise.resolve(null),
        ]);
      snapshot = {
        user,
        catalog: subjects,
        bookings,
        progress,
        notifications,
        slots,
        waitlist,
        favorites,
        admin,
      };
    }
    if (current === revision.current) {
      setCatalog(subjects);
      setData(snapshot);
      setOffline(false);
    }
  }, []);
  const initialize = useCallback(async () => {
    setFatal('');
    try {
      setConfig(await api<Config>('/config'));
      await refresh();
    } catch (e) {
      if (e instanceof SessionChanged) {
        await refresh();
      } else setFatal((e as Error).message);
    } finally {
      setReady(true);
    }
  }, [refresh]);
  useEffect(() => {
    void initialize();
    const expired = () => {
      setToken('');
      revision.current++;
      setData(null);
      navigate('/login?next=' + encodeURIComponent(location.pathname + location.search));
    };
    window.addEventListener('studymate:expired', expired);
    return () => {
      window.removeEventListener('studymate:expired', expired);
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, [initialize, navigate]);
  // Live hints: refresh the snapshot (debounced) and let open components react.
  const liveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const live = useEventStream(Boolean(data), (event) => {
    broadcast(event);
    if (event.type === 'thread') return; // the open chat reloads itself
    if (liveTimer.current) clearTimeout(liveTimer.current);
    liveTimer.current = setTimeout(() => {
      refresh().catch((e) => {
        if (!(e instanceof SessionChanged)) setOffline(true);
      });
    }, 250);
  });
  useEffect(() => {
    // With a live stream, polling is only a safety net.
    const t = setInterval(
      () => {
        if (document.visibilityState === 'visible' && hasToken() && !working)
          refresh().catch((e) => {
            if (!(e instanceof SessionChanged)) setOffline(true);
          });
      },
      live ? 60000 : 12000,
    );
    // Polling pauses in a hidden tab; catch up as soon as it is visible again.
    const visible = () => {
      if (document.visibilityState === 'visible' && hasToken() && !working)
        refresh().catch((e) => {
          if (!(e instanceof SessionChanged)) setOffline(true);
        });
    };
    document.addEventListener('visibilitychange', visible);
    return () => {
      clearInterval(t);
      document.removeEventListener('visibilitychange', visible);
    };
  }, [refresh, working, live]);
  const isPrivate = /^\/(dashboard|calendar|progress|account|team|lessons)(\/|$)/.test(path);
  useEffect(() => {
    if (ready && !fatal && isPrivate && !hasToken())
      navigate('/login?next=' + encodeURIComponent(route));
  }, [ready, fatal, isPrivate, route, navigate]);
  const mutate: Mutate = async <T,>(url: string, body: unknown, method = 'POST') => {
    setWorking(true);
    try {
      const result = await send<T>(url, body, method);
      await refresh();
      return result;
    } finally {
      setWorking(false);
    }
  };
  const favoriteIds = new Set(data?.favorites.map((m) => m.id) ?? []);
  const toggleFavorite = (mentorId: number, on: boolean) =>
    mutate('/favorites/' + mentorId, {}, on ? 'PUT' : 'DELETE').catch((e) => {
      if (!(e instanceof SessionChanged)) tell((e as Error).message);
    });
  async function authenticate(url: string, body: unknown) {
    setWorking(true);
    try {
      const result = await send<{
        token: string;
        user: User;
      }>(url, body);
      setToken(result.token);
      await refresh();
      setDemoOpen(false);
      setQuiz(null);
      const next = new URLSearchParams(query).get('next');
      navigate(
        next?.startsWith('/') && !next.startsWith('//')
          ? next
          : result.user.is_admin
            ? '/team'
            : '/dashboard',
      );
    } finally {
      setWorking(false);
    }
  }
  function forgetSession() {
    setToken('');
    revision.current++;
    setData(null);
    setQuiz(null);
    navigate('/login');
  }
  async function logout() {
    setWorking(true);
    try {
      await send('/auth/logout', {});
    } catch (e) {
      if (!(e instanceof SessionChanged)) tell((e as Error).message);
    } finally {
      setToken('');
      revision.current++;
      setData(null);
      setWorking(false);
      setQuiz(null);
      navigate('/login');
    }
  }
  async function practice(topicId: number, stage = 'practice', bookingId?: string) {
    if (!data) {
      navigate('/login?next=' + encodeURIComponent('/progress'));
      return;
    }
    try {
      const result = await mutate<Quiz>('/quizzes', {
        topic_id: topicId,
        stage,
        booking_id: bookingId,
      });
      setQuiz(result);
    } catch (e) {
      if (!(e instanceof SessionChanged)) tell((e as Error).message);
    }
  }
  if (!ready)
    return (
      <div className="boot-page">
        <Logo />
        <Busy />
      </div>
    );
  if (fatal)
    return (
      <div className="boot-page">
        <Logo />
        <ErrorText message={fatal} />
        <button className="button" onClick={() => void initialize()}>
          Попробовать ещё раз
        </button>
      </div>
    );
  const user = data?.user,
    unread = data?.notifications.filter((n) => !n.read).length || 0;
  const navItems = [
    ['/mentors', 'Найти ментора'],
    ...(user
      ? [
          [
            '/dashboard',
            user.is_admin ? 'Мои занятия' : user.mentor ? 'Мои ученики' : 'Мои занятия',
          ],
          ['/calendar', 'Календарь'],
        ]
      : [['/#how', 'Как это работает']]),
  ];
  return (
    <div className="site">
      <div className="edition-line">
        <span>СТУДЕНТЫ ОБЪЯСНЯЮТ СТУДЕНТАМ</span>
        <span>ASTANA IT UNIVERSITY / CAMPUS EDITION</span>
        {config?.mode === 'demo' && (
          <button
            onClick={() => {
              setDemoError('');
              setDemoOpen(true);
            }}
          >
            Режим защиты ↗
          </button>
        )}
      </div>
      <header className="masthead">
        <button
          className="brand-button"
          onClick={() => navigate('/')}
          aria-label="StudyMate на главную"
        >
          <Logo />
        </button>
        <nav className={menu ? 'site-nav expanded' : 'site-nav'} aria-label="Основная навигация">
          {navItems.map(([href, label]) => (
            <a
              className={path === href ? 'active' : ''}
              key={href}
              href={href}
              onClick={(e) => {
                e.preventDefault();
                if (href === '/#how') {
                  navigate('/');
                  setTimeout(
                    () => document.getElementById('how')?.scrollIntoView({ behavior: 'smooth' }),
                    60,
                  );
                } else navigate(href);
              }}
            >
              {label}
            </a>
          ))}
          <button
            className="mobile-theme"
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          >
            {theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}
          </button>
          {user?.is_admin && (
            <a
              href="/team"
              className={path === '/team' ? 'active' : ''}
              onClick={(e) => {
                e.preventDefault();
                navigate('/team');
              }}
            >
              Команда
            </a>
          )}
        </nav>
        <div className="header-tools">
          <button
            className="icon-button theme-button"
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            aria-label={theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}
          >
            {theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}
          </button>
          {user ? (
            <>
              <button
                className="icon-button bell-button"
                aria-label="Уведомления"
                onClick={() => {
                  setInboxOpen(true);
                  void mutate('/notifications/read', {}).catch((e) => tell(e.message));
                }}
              >
                <Bell size={19} />
                {unread > 0 && <i />}
              </button>
              <div className="user-control">
                <button
                  className="user-button"
                  onClick={() => setUserMenu(!userMenu)}
                  aria-label="Меню аккаунта"
                >
                  <Avatar name={user.name} id={user.id} />
                  <span>{user.name.split(' ')[0]}</span>
                  <ChevronDown size={13} />
                </button>
                {userMenu && (
                  <div className="user-dropdown">
                    <button onClick={() => navigate('/account')}>
                      <UserRound size={16} />
                      Профиль и анкета
                    </button>
                    <button onClick={() => navigate('/progress')}>Мой прогресс ↗</button>
                    <button onClick={() => void logout()} disabled={working}>
                      <LogOut size={16} />
                      Выйти из аккаунта
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <button className="button button-dark header-login" onClick={() => navigate('/login')}>
              Войти <ArrowUpRight size={16} />
            </button>
          )}
          <button
            className="icon-button menu-button"
            aria-label="Открыть меню"
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X /> : <Menu />}
          </button>
        </div>
      </header>
      {offline && (
        <div className="connection-note" role="status">
          Нет связи с локальным сервером. Сохранённые данные остаются в базе.
          <button onClick={() => refresh().catch((e) => tell(e.message))}>Повторить</button>
        </div>
      )}
      <main>
        {path === '/' && <HomePage catalog={catalog} navigate={navigate} user={user || null} />}
        {path === '/mentors' && (
          <CatalogPage
            catalog={catalog}
            query={query}
            navigate={navigate}
            userId={user?.id}
            favoriteIds={favoriteIds}
            toggleFavorite={toggleFavorite}
          />
        )}
        {/^\/mentors\/\d+$/.test(path) && (
          <MentorPage
            favorite={
              user && user.id !== Number(path.split('/')[2])
                ? {
                    active: favoriteIds.has(Number(path.split('/')[2])),
                    toggle: (on: boolean) => toggleFavorite(Number(path.split('/')[2]), on),
                  }
                : undefined
            }
            id={Number(path.split('/')[2])}
            catalog={catalog}
            query={query}
            navigate={navigate}
            user={user || null}
            mutate={mutate}
            working={working}
          />
        )}
        {(path === '/login' || path === '/register' || path === '/reset') && (
          <AuthPage
            mode={path === '/register' ? 'register' : path === '/reset' ? 'reset' : 'login'}
            query={query}
            navigate={navigate}
            working={working}
            authenticate={authenticate}
            demo={config?.mode === 'demo' ? () => setDemoOpen(true) : undefined}
          />
        )}
        {isPrivate && data && (
          <div key={data.user.id}>
            {path === '/dashboard' && (
              <DashboardPage data={data} navigate={navigate} toggleFavorite={toggleFavorite} />
            )}
            {path === '/calendar' && (
              <CalendarPage data={data} mutate={mutate} working={working} navigate={navigate} />
            )}
            {path === '/progress' && (
              <ProgressPage data={data} practice={(id) => void practice(id)} />
            )}
            {path === '/account' && (
              <AccountPage
                data={data}
                mutate={mutate}
                working={working}
                logout={() => void logout()}
                signedOut={() => {
                  forgetSession();
                  tell('Вы вышли на всех устройствах.');
                }}
              />
            )}
            {path === '/team' && (
              <TeamPage data={data} mutate={mutate} working={working} navigate={navigate} />
            )}
            {/^\/lessons\/.+$/.test(path) && (
              <LessonPage
                id={path.split('/')[2]}
                data={data}
                navigate={navigate}
                mutate={mutate}
                working={working}
                demo={config?.mode === 'demo'}
                practice={(id, stage) => void practice(id, stage, path.split('/')[2])}
              />
            )}
          </div>
        )}
        {isPrivate && !data && <Busy />}
        {![
          '/',
          '/mentors',
          '/login',
          '/register',
          '/reset',
          '/dashboard',
          '/calendar',
          '/progress',
          '/account',
          '/team',
        ].includes(path) &&
          !/^\/mentors\/\d+$/.test(path) &&
          !/^\/lessons\/.+$/.test(path) && (
            <div className="content-page">
              <h1>Такой страницы нет.</h1>
              <button className="button button-primary" onClick={() => navigate('/')}>
                На главную <ArrowUpRight size={17} />
              </button>
            </div>
          )}
      </main>
      <footer className="site-footer">
        <div>
          <Logo />
          <p>
            Учиться проще,
            <br />
            <em>когда есть с кем.</em>
          </p>
        </div>
        <div>
          <span className="mono">НА СВОЁМ КАМПУСЕ</span>
          <a
            href="/mentors"
            onClick={(e) => {
              e.preventDefault();
              navigate('/mentors');
            }}
          >
            Найти ментора ↗
          </a>
          <a
            href="/account"
            onClick={(e) => {
              e.preventDefault();
              navigate('/account');
            }}
          >
            Стать ментором ↗
          </a>
        </div>
        <div>
          <span className="mono">МАЛЕНЬКИЙ ПРОЕКТ. БОЛЬШАЯ ПОДДЕРЖКА.</span>
          <p>
            Сделано для студентов AITU.
            <br />
            Время встреч — Алматы, UTC+5.
          </p>
          {config?.mode === 'demo' && (
            <small>
              Профили демонстрации вымышлены.
              <br />
              Оплата моделируется без списаний.
            </small>
          )}
        </div>
        <div className="footer-bottom">
          <span>© StudyMate / 2026</span>
          <span>Меньше паники. Больше понимания.</span>
          <span>✳</span>
        </div>
      </footer>
      {toast && (
        <div className="toast" role="status">
          <span>{toast}</span>
          <button onClick={() => setToast('')} aria-label="Скрыть сообщение">
            <X size={16} />
          </button>
        </div>
      )}
      {demoOpen && (
        <Modal title="Посмотреть с другой стороны" close={() => setDemoOpen(false)}>
          <p className="muted">
            Отдельные учебные аккаунты для демонстрации. Каждый показывает свою сторону одной
            записи.
          </p>
          <div className="demo-accounts">
            {config?.demo_accounts.map((a) => (
              <button
                disabled={working}
                key={a.id}
                onClick={() => {
                  setDemoError('');
                  void authenticate('/auth/demo', { user_id: a.id }).catch((e) =>
                    setDemoError(e.message),
                  );
                }}
              >
                <Avatar name={a.name} id={a.id} />
                <span>
                  <strong>{a.name}</strong>
                  <small>{a.role}</small>
                </span>
                <ArrowUpRight size={19} />
              </button>
            ))}
          </div>
          <ErrorText message={demoError} />
        </Modal>
      )}
      {inboxOpen && (
        <Modal title="Что нового" close={() => setInboxOpen(false)}>
          <div className="notice-list">
            {data?.notifications.length ? (
              data.notifications
                .filter((n) => n.status !== 'skipped')
                .map((n) => (
                  <button
                    key={n.id}
                    onClick={() => {
                      if (n.link) {
                        setInboxOpen(false);
                        navigate(n.link);
                      } else if (n.booking_id) {
                        setInboxOpen(false);
                        navigate('/lessons/' + n.booking_id);
                      }
                    }}
                  >
                    <span className="notice-mark">↗</span>
                    <span>
                      {n.body}
                      <small>{n.kind === 'reminder' ? 'Напоминание' : 'StudyMate'}</small>
                    </span>
                  </button>
                ))
            ) : (
              <p className="muted">
                Здесь появятся заявки, подтверждения и напоминания о встречах.
              </p>
            )}
          </div>
        </Modal>
      )}
      {quiz && (
        <QuizDialog
          key={quiz.id}
          quiz={quiz}
          working={working}
          close={() => setQuiz(null)}
          submit={async (answers) => {
            setQuiz(await mutate<Quiz>('/quizzes/' + quiz.id + '/submit', { answers }));
          }}
        />
      )}
    </div>
  );
}
