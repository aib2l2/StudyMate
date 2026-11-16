import { useEffect, useRef, useState } from 'react';
import { send } from './api';

/** A hint from the server that something changed; the data is re-fetched via the API. */
export type LiveEvent = { type: string; id?: string };

export const LIVE_EVENT = 'studymate:live';
const MAX_DELAY = 30_000;

/** Fan a server hint out to components (e.g. the open chat). */
export function broadcast(event: LiveEvent) {
  window.dispatchEvent(new CustomEvent<LiveEvent>(LIVE_EVENT, { detail: event }));
}

export function onLive(listener: (event: LiveEvent) => void) {
  const handler = (e: Event) => listener((e as CustomEvent<LiveEvent>).detail);
  window.addEventListener(LIVE_EVENT, handler);
  return () => window.removeEventListener(LIVE_EVENT, handler);
}

/**
 * Keeps an EventSource open while `enabled` and the tab is visible.
 *
 * EventSource cannot send an Authorization header, so each connection first
 * exchanges the session for a single-use ticket. Its built-in reconnect would
 * reuse a spent ticket, so reconnects are handled here with exponential
 * backoff (1 s … 30 s). Returns whether the stream is currently connected.
 */
export function useEventStream(enabled: boolean, onEvent: (event: LiveEvent) => void): boolean {
  const [connected, setConnected] = useState(false);
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (!enabled) return;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let stopped = false;

    const close = () => {
      source?.close();
      source = null;
      setConnected(false);
    };
    const schedule = () => {
      if (stopped) return;
      clearTimeout(timer);
      const delay = Math.min(MAX_DELAY, 1000 * 2 ** attempt);
      attempt += 1;
      timer = setTimeout(() => void open(), delay);
    };
    const open = async () => {
      if (stopped || source || document.visibilityState !== 'visible') return;
      try {
        const { ticket } = await send<{ ticket: string }>('/events/ticket', {});
        if (stopped || document.visibilityState !== 'visible') return;
        const current = new EventSource('/api/events?ticket=' + encodeURIComponent(ticket));
        source = current;
        current.onopen = () => {
          attempt = 0;
          setConnected(true);
        };
        current.onmessage = (message) => {
          try {
            handler.current(JSON.parse(message.data) as LiveEvent);
          } catch {
            // A malformed hint is ignored; polling still keeps data fresh.
          }
        };
        current.addEventListener('session_ended', () => {
          close();
          handler.current({ type: 'session_ended' });
        });
        current.onerror = () => {
          if (source !== current) return;
          close();
          schedule();
        };
      } catch {
        schedule();
      }
    };
    const visibility = () => {
      if (document.visibilityState === 'visible') {
        attempt = 0;
        void open();
      } else {
        clearTimeout(timer);
        close();
      }
    };

    void open();
    document.addEventListener('visibilitychange', visibility);
    return () => {
      stopped = true;
      clearTimeout(timer);
      close();
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [enabled]);

  return connected;
}
