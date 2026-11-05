import assert from 'node:assert/strict';
import test from 'node:test';
import type { DomainEvent } from '../src/api/simulation.ts';
import { appendContiguousEvents, findAppliedNotice, makeNoticeRequest } from '../src/features/workbench/event-state.ts';

function event(seq: number, overrides: Partial<DomainEvent> = {}): DomainEvent {
  return {
    event_id: `evt-${seq}`, run_id: 'run-a', seq, type: 'NoticePublished',
    schema_version: 1, sim_time_ms: 0, occurred_at: '2026-11-05T00:00:00Z',
    correlation_id: 'cmd-a', causation_id: 'cmd-a', payload: { content: '活动通知' },
    ...overrides,
  };
}

test('incremental pages stay ordered and duplicate deliveries have one effect', () => {
  const first = appendContiguousEvents({ items: [], lastSeq: 0 }, [event(2), event(1)], 'run-a');
  const second = appendContiguousEvents(first, [event(2), event(3), event(3)], 'run-a');
  assert.deepEqual(second.items.map((item) => item.seq), [1, 2, 3]);
  assert.equal(second.lastSeq, 3);
  assert.equal(first.lastSeq, 2);
});

test('a missing seq never advances the saved cursor or mutates cached events', () => {
  const original = { items: [event(1)], lastSeq: 1 };
  assert.throws(() => appendContiguousEvents(original, [event(2), event(4)], 'run-a'), /不连续/);
  assert.equal(original.lastSeq, 1);
  assert.equal(original.items.length, 1);
});

test('a seq collision or changed event sequence is rejected', () => {
  const original = { items: [event(1)], lastSeq: 1 };
  assert.throws(() => appendContiguousEvents(original, [event(1, { event_id: 'evt-other' })], 'run-a'), /不同事件/);
  assert.throws(() => appendContiguousEvents(original, [event(2, { event_id: 'evt-1' })], 'run-a'), /序号发生变化/);
});

test('a stale response from another run cannot enter the selected feed', () => {
  assert.throws(() => appendContiguousEvents({ items: [], lastSeq: 0 }, [event(1, { run_id: 'run-b' })], 'run-a'), /其他运行/);
});

test('only a NoticePublished caused by this exact command proves application', () => {
  assert.equal(findAppliedNotice([], 'cmd-a'), undefined);
  assert.equal(findAppliedNotice([event(1, { causation_id: 'cmd-b' })], 'cmd-a'), undefined);
  assert.equal(findAppliedNotice([event(1, { type: 'ActionRejected' })], 'cmd-a'), undefined);
  assert.equal(findAppliedNotice([event(1)], undefined), undefined);
  assert.equal(findAppliedNotice([event(1)], 'cmd-a')?.event_id, 'evt-1');
});

test('reusing a request preserves its identifier and exact original notice text', () => {
  const text = '  本周读书会\n请准时参加。 ';
  const request = makeNoticeRequest(text, 'request-original');
  assert.equal(JSON.stringify(request), JSON.stringify(makeNoticeRequest(text, 'request-original')));
  assert.equal(request.payload.content, text);
  assert.deepEqual(request.payload.recipient_agent_ids, []);
  assert.equal(request.type, 'PublishNotice');
  assert.equal(request.schema_version, 1);
});
