import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FavoriteButton } from './FavoriteButton';

afterEach(cleanup);

describe('FavoriteButton', () => {
  it('announces state and asks for the opposite on click', async () => {
    const toggle = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(<FavoriteButton name="Аяулым" active={false} toggle={toggle} />);
    const button = screen.getByRole('button', { name: 'Добавить Аяулым в избранное' });
    expect(button.getAttribute('aria-pressed')).toBe('false');
    await userEvent.click(button);
    expect(toggle).toHaveBeenCalledWith(true);
    rerender(<FavoriteButton name="Аяулым" active toggle={toggle} />);
    await userEvent.click(screen.getByRole('button', { name: 'Убрать Аяулым из избранного' }));
    expect(toggle).toHaveBeenLastCalledWith(false);
  });
});
