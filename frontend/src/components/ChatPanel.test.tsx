import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ChatPanel } from './ChatPanel';

const thread = (messages: object[] = []) => ({
  thread: 'booking:b1',
  can_write: true,
  messages,
  my_last_read_id: 0,
  others_last_read_id: 0,
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function server(postStatus: number[]) {
  const posts: unknown[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/messages') && init?.method === 'POST') {
        posts.push(JSON.parse(String(init.body)));
        const status = postStatus.shift() ?? 200;
        return new Response(
          JSON.stringify(status === 200 ? { id: 1 } : { detail: 'Сервер недоступен' }),
          { status },
        );
      }
      return new Response(JSON.stringify(thread()));
    }),
  );
  return posts;
}

describe('ChatPanel', () => {
  it('sends on Enter and keeps a new line on Shift+Enter', async () => {
    const posts = server([200]);
    render(<ChatPanel bookingId="b1" userId={1} />);
    const box = await screen.findByLabelText(/Сообщение/);
    await userEvent.type(box, 'Первая{Shift>}{Enter}{/Shift}вторая');
    expect(posts).toHaveLength(0);
    expect((box as HTMLTextAreaElement).value).toBe('Первая\nвторая');
    await userEvent.type(box, '{Enter}');
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]).toMatchObject({ body: 'Первая\nвторая' });
  });

  it('offers a retry with the same client id after a failed send', async () => {
    const posts = server([500, 200]) as { client_id: string }[];
    render(<ChatPanel bookingId="b1" userId={1} />);
    await userEvent.type(await screen.findByLabelText(/Сообщение/), 'Вопрос{Enter}');
    const retry = await screen.findByRole('button', { name: /Повторить/ });
    await userEvent.click(retry);
    await waitFor(() => expect(posts).toHaveLength(2));
    expect(posts[1].client_id).toBe(posts[0].client_id); // idempotent on the server
  });

  it('shows a read-only note when the chat is closed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ ...thread(), can_write: false }))),
    );
    render(<ChatPanel bookingId="b1" userId={1} />);
    expect(await screen.findByText(/можно только читать/)).toBeTruthy();
    expect(screen.queryByLabelText(/Сообщение/)).toBeNull();
  });
});
