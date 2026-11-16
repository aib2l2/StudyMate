import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setToken } from './api';
import { useEventStream, type LiveEvent } from './live';

class FakeSource {
  static all: FakeSource[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Record<string, () => void> = {};
  closed = false;
  constructor(public url: string) {
    FakeSource.all.push(this);
  }
  addEventListener(name: string, fn: () => void) {
    this.listeners[name] = fn;
  }
  close() {
    this.closed = true;
  }
}

function Probe({
  onEvent,
  onState,
}: {
  onEvent: (e: LiveEvent) => void;
  onState: (c: boolean) => void;
}) {
  onState(useEventStream(true, onEvent));
  return null;
}

const flush = () => act(async () => await Promise.resolve());

beforeEach(() => {
  FakeSource.all = [];
  vi.useFakeTimers();
  vi.stubGlobal('EventSource', FakeSource);
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ ticket: 't-' + FakeSource.all.length }))),
  );
  setToken('token');
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  setToken('');
});

describe('useEventStream', () => {
  it('exchanges a ticket, reports connection and forwards hints', async () => {
    const events: LiveEvent[] = [];
    const states: boolean[] = [];
    render(<Probe onEvent={(e) => events.push(e)} onState={(c) => states.push(c)} />);
    await flush();
    await flush();
    const source = FakeSource.all[0];
    expect(source.url).toBe('/api/events?ticket=t-0');
    act(() => source.onopen?.());
    expect(states.at(-1)).toBe(true);
    act(() => source.onmessage?.({ data: '{"type":"thread","id":"booking:1"}' }));
    expect(events).toEqual([{ type: 'thread', id: 'booking:1' }]);
  });

  it('reconnects with a fresh ticket and growing delay', async () => {
    render(<Probe onEvent={() => {}} onState={() => {}} />);
    await flush();
    await flush();
    act(() => FakeSource.all[0].onerror?.());
    expect(FakeSource.all[0].closed).toBe(true);
    await act(async () => vi.advanceTimersByTime(999));
    expect(FakeSource.all).toHaveLength(1);
    await act(async () => vi.advanceTimersByTime(1));
    await flush();
    expect(FakeSource.all).toHaveLength(2);
    act(() => FakeSource.all[1].onerror?.());
    await act(async () => vi.advanceTimersByTime(1999));
    expect(FakeSource.all).toHaveLength(2); // second retry waits 2 s
    await act(async () => vi.advanceTimersByTime(1));
    await flush();
    expect(FakeSource.all).toHaveLength(3);
  });

  it('closes in a hidden tab and reopens when visible', async () => {
    render(<Probe onEvent={() => {}} onState={() => {}} />);
    await flush();
    await flush();
    const visibility = vi.spyOn(document, 'visibilityState', 'get');
    visibility.mockReturnValue('hidden');
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    expect(FakeSource.all[0].closed).toBe(true);
    visibility.mockReturnValue('visible');
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    await flush();
    await flush();
    expect(FakeSource.all).toHaveLength(2);
    visibility.mockRestore();
  });

  it('reports a session ended by the server', async () => {
    const events: LiveEvent[] = [];
    render(<Probe onEvent={(e) => events.push(e)} onState={() => {}} />);
    await flush();
    await flush();
    act(() => FakeSource.all[0].listeners.session_ended());
    expect(events).toEqual([{ type: 'session_ended' }]);
  });
});
