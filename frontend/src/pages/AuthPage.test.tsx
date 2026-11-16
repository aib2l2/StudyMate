import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthPage } from './AuthPage';

afterEach(cleanup);

describe('AuthPage', () => {
  it('submits the reset code with a new password', async () => {
    const authenticate = vi.fn().mockResolvedValue(undefined);
    render(
      <AuthPage
        mode="reset"
        query=""
        navigate={vi.fn()}
        working={false}
        authenticate={authenticate}
      />,
    );
    await userEvent.type(screen.getByLabelText('Email'), 'me@example.test');
    await userEvent.type(screen.getByLabelText('Код от владельца сайта'), 'AB12-CD34-EF56');
    await userEvent.type(screen.getByLabelText(/^Новый пароль/), 'new-password-1');
    await userEvent.click(screen.getByRole('button', { name: /Сохранить и войти/ }));
    expect(authenticate).toHaveBeenCalledWith('/auth/reset', {
      email: 'me@example.test',
      code: 'AB12-CD34-EF56',
      new_password: 'new-password-1',
    });
  });

  it('shows a server error inside the form and links it to the fields', async () => {
    const authenticate = vi.fn().mockRejectedValue(new Error('Email или пароль не совпадают'));
    render(
      <AuthPage
        mode="login"
        query=""
        navigate={vi.fn()}
        working={false}
        authenticate={authenticate}
      />,
    );
    await userEvent.type(screen.getByLabelText('Email'), 'me@example.test');
    await userEvent.type(screen.getByLabelText('Пароль'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: /Войти/ }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('не совпадают');
    expect(screen.getByLabelText('Email').getAttribute('aria-describedby')).toBe(alert.id);
  });

  it('offers password recovery from the login form', async () => {
    const navigate = vi.fn();
    render(
      <AuthPage
        mode="login"
        query="?next=/calendar"
        navigate={navigate}
        working={false}
        authenticate={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByText('Забыли пароль?'));
    expect(navigate).toHaveBeenCalledWith('/reset?next=/calendar');
  });
});
