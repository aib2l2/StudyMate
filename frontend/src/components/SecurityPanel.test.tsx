import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { User } from '../types';
import { SecurityPanel } from './SecurityPanel';

const user: User = {
  id: 7,
  name: 'Тест',
  email: 'me@example.test',
  campus: 'Astana IT University',
  course: 2,
  languages: ['ru'],
  interests: [],
  registered: true,
  is_admin: false,
  mentor: null,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('SecurityPanel', () => {
  it('blocks submission while the repeated password differs', async () => {
    render(<SecurityPanel user={user} signedOut={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/^Новый пароль/), 'new-password-1');
    await userEvent.type(screen.getByLabelText('Повторите новый пароль'), 'new-password-2');
    expect(screen.getByText('Пароли не совпадают.')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Сменить пароль/ }).hasAttribute('disabled')).toBe(
      true,
    );
  });

  it('signs out locally after logging out everywhere', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 })));
    const signedOut = vi.fn();
    render(<SecurityPanel user={user} signedOut={signedOut} />);
    await userEvent.click(screen.getByRole('button', { name: /Выйти на всех устройствах/ }));
    expect(signedOut).toHaveBeenCalledOnce();
  });

  it('explains that demo accounts have no password', () => {
    render(<SecurityPanel user={{ ...user, email: null }} signedOut={vi.fn()} />);
    expect(screen.queryByLabelText('Текущий пароль')).toBeNull();
  });
});
