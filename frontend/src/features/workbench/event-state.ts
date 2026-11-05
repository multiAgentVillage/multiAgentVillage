import type { DomainEvent } from '../../api/simulation.ts';

export interface EventFeed {
  items: DomainEvent[];
  lastSeq: number;
}

/** Never skip a missing seq: the next request must still start before the gap. */
export function appendContiguousEvents(feed: EventFeed, incoming: DomainEvent[], runId: string): EventFeed {
  const byId = new Map(feed.items.map((event) => [event.event_id, event]));
  const bySeq = new Map(feed.items.map((event) => [event.seq, event.event_id]));
  const items = [...feed.items];
  let lastSeq = feed.lastSeq;
  for (const event of [...incoming].sort((a, b) => a.seq - b.seq)) {
    if (event.run_id !== runId) throw new Error('收到其他运行的事件，已停止合并。');
    if (byId.has(event.event_id)) {
      if (byId.get(event.event_id)?.seq !== event.seq) throw new Error('事件标识对应的序号发生变化。');
      continue;
    }
    if (bySeq.has(event.seq)) throw new Error('同一事件序号对应了不同事件。');
    if (event.seq !== lastSeq + 1) throw new Error('事件暂不连续，正在等待完整补拉。');
    items.push(event);
    byId.set(event.event_id, event);
    bySeq.set(event.seq, event.event_id);
    lastSeq = event.seq;
  }
  return { items, lastSeq };
}

/** A command receipt alone is insufficient proof that the notice took effect. */
export function findAppliedNotice(events: DomainEvent[], commandId: string | undefined) {
  return commandId ? events.find((event) =>
    event.type === 'NoticePublished' && event.causation_id === commandId,
  ) : undefined;
}

export function makeNoticeRequest(content: string, requestId: string) {
  return {
    request_id: requestId, type: 'PublishNotice' as const, schema_version: 1 as const,
    payload: { content, recipient_agent_ids: [] as string[] },
  };
}

/** Request IDs are correlation keys, including when a teaching host uses HTTP. */
export function newRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const entropy = globalThis.crypto?.getRandomValues(new Uint32Array(4));
  return `request-${Date.now().toString(36)}-${entropy
    ? Array.from(entropy, (part) => part.toString(16).padStart(8, '0')).join('')
    : `${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`}`;
}
