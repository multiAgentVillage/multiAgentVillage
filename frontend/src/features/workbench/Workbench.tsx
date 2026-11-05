import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Col, Empty, Row, Space, Spin, Tag, Typography } from 'antd';
import { getAgent, getRunState } from '../../api/simulation';
import type { DomainEvent, RunStatus } from '../../api/simulation';
import { useUiStore } from '../../stores/ui-store';
import { NoticeComposer } from './NoticeComposer';
import { useEventFeed, useRunUpdates } from './useEventFeed';
import type { ConnectionState } from './useEventFeed';

const statusNames: Record<RunStatus, string> = {
  DRAFT: '草稿', READY: '就绪', RUNNING: '运行中', PAUSED: '已暂停', FINISHED: '已结束', FAILED: '运行失败',
};
const connectionNames: Record<ConnectionState, string> = {
  connecting: '正在连接', connected: '实时连接正常', reconnecting: '正在重连 · 定时补拉中', offline: '网络离线 · 等待恢复',
};

export function simTime(ms: number) {
  const seconds = Math.floor(ms / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

function EventTimeline({ events }: { events: DomainEvent[] }) {
  if (!events.length) return <Empty description="还没有事件。发布一条通知，观察它如何生效。" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  return (
    <ol className="event-timeline" data-testid="event-timeline">
      {[...events].reverse().map((event) => (
        <li key={event.event_id} data-testid={`event-${event.event_id}`} data-command-id={event.causation_id}>
          <div className="event-marker" />
          <div className="event-body">
            <div className="event-heading">
              <strong>{event.type === 'NoticePublished' ? '活动通知已发布' : event.type}</strong>
              <span>#{event.seq} · {simTime(event.sim_time_ms)}</span>
            </div>
            {event.type === 'NoticePublished' && typeof event.payload.content === 'string' && <p className="notice-text">{event.payload.content}</p>}
            <Typography.Text type="secondary" className="event-cause">命令 {event.causation_id}</Typography.Text>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function Workbench({ runId }: { runId: string }) {
  const state = useQuery({
    queryKey: ['run', runId], queryFn: ({ signal }) => getRunState(runId, signal),
    refetchInterval: 2_000, refetchOnWindowFocus: true,
  });
  const events = useEventFeed(runId);
  const connection = useRunUpdates(runId);
  const selectedAgentId = useUiStore((value) => value.selectedAgentId);
  const selectAgent = useUiStore((value) => value.selectAgent);
  const selected = state.data?.agents.find((agent) => agent.agent_id === selectedAgentId)
    ?? state.data?.agents.find((agent) => agent.name === '陈宇') ?? state.data?.agents[0];
  const memories = useQuery({
    queryKey: ['agent', runId, selected?.agent_id],
    queryFn: ({ signal }) => getAgent(runId, selected!.agent_id, signal),
    enabled: Boolean(selected), refetchInterval: 2_000, refetchOnWindowFocus: true,
  });

  if (state.isPending) return <Card><Spin description="正在读取当前运行…" /></Card>;
  if (!state.data) return (
    <Alert type="error" showIcon title="无法读取运行" description={state.error?.message}
      action={<Button onClick={() => void state.refetch()}>重新获取</Button>} />
  );
  const run = state.data;

  return (
    <Space orientation="vertical" size={24} style={{ width: '100%' }}>
      <Card className="run-overview" styles={{ body: { paddingBlock: 20 } }}>
        <div className="overview-top">
          <div>
            <Typography.Text className="eyebrow">当前运行</Typography.Text>
            <h2>{run.name}</h2>
            <Typography.Text type="secondary" className="trace-id">{run.run_id}</Typography.Text>
          </div>
          <div className="connection-state" role="status" data-testid="stream-status">
            <span className={`connection-dot ${connection === 'connected' ? 'is-connected' : ''}`} />
            {connectionNames[connection]}
          </div>
        </div>
        <div className="run-stats">
          <div><span>运行状态</span><strong data-testid="run-status">{statusNames[run.status]}</strong></div>
          <div><span>校园地点</span><strong>{run.locations.length}<small>个</small></strong></div>
          <div><span>参与角色</span><strong>{run.agents.length}<small>名</small></strong></div>
          <div><span>已同步事件</span><strong data-testid="event-cursor">{events.data?.lastSeq ?? 0}<small>条</small></strong></div>
        </div>
      </Card>
      {state.isError && <Alert type="warning" showIcon title="运行状态暂时无法刷新，当前展示上次读取的结果。" description={state.error.message} />}
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={15}>
          <Space orientation="vertical" size={24} style={{ width: '100%' }}>
            <NoticeComposer runId={runId} status={run.status} events={events.data?.items ?? []} />
            <Card title="事件时间线" extra={<Button size="small" loading={events.isFetching}
              onClick={() => void events.refetch()}>补拉事件</Button>}>
              <Typography.Paragraph type="secondary" className="section-intro">展示已生效的事实。断线后按事件序号补齐，最新事件在上方。</Typography.Paragraph>
              {events.isError && <Alert type="warning" showIcon title="事件同步暂时失败，将自动重试。" description={events.error.message} />}
              {events.isPending ? <Spin description="正在补拉事件…" /> : <EventTimeline events={events.data?.items ?? []} />}
            </Card>
          </Space>
        </Col>
        <Col xs={24} lg={9}>
          <Space orientation="vertical" size={24} style={{ width: '100%' }}>
            <Card title="校园角色" extra={<Typography.Text type="secondary">{run.agents.length}名</Typography.Text>}>
              <div className="agent-grid" data-testid="agent-list">
                {run.agents.map((agent) => (
                  <button type="button" key={agent.agent_id} aria-pressed={agent.agent_id === selected?.agent_id}
                    aria-label={`查看${agent.name}的记忆`} onClick={() => selectAgent(agent.agent_id)}
                    className={`agent-button ${agent.agent_id === selected?.agent_id ? 'is-selected' : ''}`}>
                    <span className="agent-avatar">{agent.name.slice(0, 1)}</span>
                    <span><strong>{agent.name}</strong><small>{agent.location_name ?? '位置未知'}</small></span>
                  </button>
                ))}
              </div>
              <div className="location-list" aria-label="校园地点">
                {run.locations.map((location) => <Tag key={location.location_id} color={location.is_open ? undefined : 'red'}>
                  {location.name}{location.is_open ? '' : ' · 关闭'}
                </Tag>)}
              </div>
            </Card>
            <Card title={selected ? `${selected.name}的观察记忆` : '观察记忆'} extra={<Tag>{memories.data?.memories.length ?? 0}条</Tag>}>
              <Typography.Paragraph type="secondary" className="section-intro">选择角色，查看其从通知中获得的信息。</Typography.Paragraph>
              {memories.isError && <Alert type="warning" showIcon title="记忆暂时无法刷新，将自动重试。" description={memories.error.message} />}
              {memories.isPending && selected ? <Spin description="正在读取记忆…" />
                : !memories.data?.memories.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂时没有观察记忆。通知生效后请稍候。" />
                  : <ul className="memory-list" data-testid="memory-list">
                    {memories.data.memories.map((memory) => <li key={memory.memory_id}>
                      <p>{memory.content}</p><span>{simTime(memory.sim_time_ms)} · 来源事件</span>
                      <Typography.Text className="trace-id">{memory.source_event_id}</Typography.Text>
                    </li>)}
                  </ul>}
            </Card>
          </Space>
        </Col>
      </Row>
    </Space>
  );
}
