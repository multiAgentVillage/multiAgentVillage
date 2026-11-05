import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Input, Space, Tag, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { ApiError } from '../../api/client';
import { getCommand, publishNotice } from '../../api/simulation';
import type { DomainEvent, NoticeRequest, RunStatus } from '../../api/simulation';
import { findAppliedNotice, makeNoticeRequest, newRequestId } from './event-state';

interface Attempt {
  request: NoticeRequest;
  commandId?: string;
  phase: 'sending' | 'accepted' | 'uncertain' | 'rejected' | 'error';
  reason?: string;
}

function restoreAttempt(runId: string): Attempt | undefined {
  try {
    const value = JSON.parse(sessionStorage.getItem(`notice-attempt:${runId}`) ?? 'null') as Attempt | null;
    if (!value || typeof value.request?.request_id !== 'string'
      || value.request.type !== 'PublishNotice' || value.request.schema_version !== 1
      || typeof value.request.payload?.content !== 'string'
      || !Array.isArray(value.request.payload.recipient_agent_ids)
      || value.request.payload.recipient_agent_ids.length !== 0
      || !['sending', 'accepted', 'uncertain', 'rejected', 'error'].includes(value.phase)) return undefined;
    if (value.commandId !== undefined && typeof value.commandId !== 'string') return undefined;
    return { ...value, phase: value.phase === 'sending' ? 'uncertain' : value.phase };
  } catch { return undefined; }
}

export function NoticeComposer({ runId, status, events }: {
  runId: string; status: RunStatus; events: DomainEvent[];
}) {
  const client = useQueryClient();
  const [attempt, setAttempt] = useState<Attempt | undefined>(() => restoreAttempt(runId));
  const [content, setContent] = useState(() => restoreAttempt(runId)?.request.payload.content
    ?? '读书会将在活动室举行，欢迎同学们参加。');
  const appliedEvent = findAppliedNotice(events, attempt?.commandId);
  const mutation = useMutation({
    mutationFn: (request: NoticeRequest) => publishNotice(runId, request), retry: false,
  });
  const receipt = useQuery({
    queryKey: ['command', runId, attempt?.commandId],
    queryFn: ({ signal }) => getCommand(runId, attempt!.commandId!, signal),
    enabled: Boolean(attempt?.commandId && !appliedEvent && attempt.phase !== 'rejected'),
    refetchInterval: 2_000, refetchOnWindowFocus: true,
  });

  useEffect(() => {
    try {
      if (attempt) sessionStorage.setItem(`notice-attempt:${runId}`, JSON.stringify(attempt));
    } catch { /* A blocked sessionStorage must not prevent publication. */ }
  }, [attempt, runId]);

  useEffect(() => {
    if (receipt.data?.status === 'rejected') {
      const reason = receipt.data.reason ?? '通知未通过运行规则校验。';
      setAttempt((current) => current ? { ...current, phase: 'rejected', reason } : current);
    }
  }, [receipt.data?.status, receipt.data?.reason]);

  async function send(request: NoticeRequest) {
    setAttempt({ request, phase: 'sending' });
    try {
      const result = await mutation.mutateAsync(request);
      setAttempt({
        request, commandId: result.command_id,
        phase: result.status === 'rejected' ? 'rejected' : 'accepted',
        reason: result.reason ?? undefined,
      });
      void client.invalidateQueries({ queryKey: ['events', runId] });
    } catch (error) {
      const uncertain = !(error instanceof ApiError) || !error.status || error.status >= 500;
      setAttempt({
        request, phase: uncertain ? 'uncertain' : 'error',
        reason: error instanceof ApiError && error.status === 409
          ? '请求标识已被用于不同内容，发生冲突。请新建一条通知。'
          : error instanceof Error ? error.message : '无法提交通知。',
      });
    }
  }

  const waiting = !appliedEvent && (attempt?.phase === 'sending' || attempt?.phase === 'accepted');
  const locked = waiting || attempt?.phase === 'uncertain';
  const label = appliedEvent ? '已生效'
    : attempt?.phase === 'accepted' ? '已接收'
    : attempt?.phase === 'rejected' ? '已拒绝'
    : attempt?.phase === 'sending' ? '提交中'
    : attempt?.phase === 'uncertain' ? '等待确认' : '提交失败';
  const type = appliedEvent ? 'success' : attempt?.phase === 'error' || attempt?.phase === 'rejected'
    ? 'error' : attempt?.phase === 'uncertain' ? 'warning' : 'info';

  return (
    <Card title="发布活动通知" className="notice-card" extra={<Tag color="cyan">全体角色</Tag>}>
      <form onSubmit={(event) => {
        event.preventDefault();
        if (!locked && content.trim() && status === 'RUNNING') {
          void send(makeNoticeRequest(content, newRequestId()));
        }
      }}>
        <label className="field-label" htmlFor="notice-content">通知内容</label>
        <Input.TextArea id="notice-content" value={content} onChange={(event) => setContent(event.target.value)}
          rows={3} maxLength={2000} showCount disabled={locked}
          placeholder="例如：读书会将在活动室举行，欢迎同学们参加。" />
        <div className="composer-actions">
          <Typography.Text type="secondary">通知生效后，角色会分别形成观察记忆。</Typography.Text>
          <Button type="primary" htmlType="submit" aria-label="发布全体通知"
            aria-busy={attempt?.phase === 'sending'} loading={attempt?.phase === 'sending'}
            disabled={locked || !content.trim() || status !== 'RUNNING'}>发布全体通知</Button>
        </div>
        {status !== 'RUNNING' && <Alert type="warning" showIcon title="当前运行未处于运行中状态，暂不能发布通知。" />}
      </form>
      {attempt && (
        <div className="notice-feedback" aria-live="polite" data-testid="command-feedback">
          <Alert type={type} showIcon title={<span data-testid="command-status">{label}</span>}
            description={
              <Space orientation="vertical" size={5} style={{ width: '100%' }}>
                <span>{appliedEvent ? `通知已生效，对应事件 #${appliedEvent.seq}。`
                  : attempt.phase === 'accepted' ? '命令已保存，正在等待对应的权威事件。'
                    : attempt.phase === 'sending' ? '正在提交通知…'
                      : attempt.phase === 'uncertain' ? '尚未确认服务端是否已接收。重试会沿用原请求标识与原内容。'
                        : attempt.reason}</span>
                {attempt.phase === 'uncertain' && attempt.reason && <Typography.Text type="secondary">{attempt.reason}</Typography.Text>}
                <Typography.Text className="trace-id" data-testid="command-id">
                  {attempt.commandId ? `命令 ${attempt.commandId}` : `请求 ${attempt.request.request_id}`}
                </Typography.Text>
                {attempt.phase === 'uncertain' && <Button onClick={() => void send(attempt.request)}>重试原请求</Button>}
                {receipt.isError && !appliedEvent && <Typography.Text type="warning">回执查询暂时失败，将自动重试：{receipt.error.message}</Typography.Text>}
              </Space>
            } />
        </div>
      )}
    </Card>
  );
}
