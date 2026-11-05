import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useState } from 'react';
import { listEvents } from '../../api/simulation';
import { appendContiguousEvents } from './event-state';
import type { EventFeed } from './event-state';

export function useEventFeed(runId: string) {
  const client = useQueryClient();
  const queryKey = ['events', runId];
  return useQuery({
    queryKey,
    queryFn: async ({ signal }) => {
      let feed = client.getQueryData<EventFeed>(['events', runId]) ?? { items: [], lastSeq: 0 };
      // Bound each catch-up task; periodic refetch resumes from this verified cursor.
      for (let pageCount = 0; pageCount < 10; pageCount += 1) {
        const page = await listEvents(runId, feed.lastSeq, signal);
        const previousSeq = feed.lastSeq;
        feed = appendContiguousEvents(feed, page.items, runId);
        if (!page.has_more) break;
        if (previousSeq === feed.lastSeq) throw new Error('事件补拉未取得进展，请稍后重试。');
      }
      return feed;
    },
    refetchInterval: 2_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    retry: 1,
    staleTime: 0,
  });
}

export type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'offline';

/** WebSocket messages only wake REST catch-up; no event or seq is trusted here. */
export function useRunUpdates(runId: string) {
  const client = useQueryClient();
  const [connection, setConnection] = useState<ConnectionState>('connecting');
  const catchUp = useCallback(() => {
    void client.invalidateQueries({ queryKey: ['events', runId] });
    void client.invalidateQueries({ queryKey: ['run', runId] });
  }, [client, runId]);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    const connect = () => {
      if (disposed) return;
      setConnection(navigator.onLine ? 'connecting' : 'offline');
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const activeSocket = new WebSocket(`${protocol}//${window.location.host}/ws/runs/${encodeURIComponent(runId)}/updates`);
      socket = activeSocket;
      activeSocket.onopen = () => {
        if (disposed) return;
        failures = 0;
        setConnection('connected');
        catchUp();
      };
      activeSocket.onmessage = () => { if (!disposed) catchUp(); };
      activeSocket.onerror = () => activeSocket.close();
      activeSocket.onclose = () => {
        if (disposed) return;
        setConnection(navigator.onLine ? 'reconnecting' : 'offline');
        failures += 1;
        retry = setTimeout(connect, Math.min(1_000 * 2 ** Math.min(failures - 1, 4), 15_000));
      };
    };
    const online = () => { catchUp(); socket?.close(); };
    const offline = () => { setConnection('offline'); };
    const focus = () => catchUp();
    connect();
    window.addEventListener('online', online);
    window.addEventListener('offline', offline);
    window.addEventListener('focus', focus);
    return () => {
      disposed = true;
      clearTimeout(retry);
      window.removeEventListener('online', online);
      window.removeEventListener('offline', offline);
      window.removeEventListener('focus', focus);
      if (socket) {
        socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null;
        socket.close();
      }
    };
  }, [catchUp, runId]);

  return connection;
}
