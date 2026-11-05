import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Empty, Layout, Select, Space, Spin, Tag, Typography } from 'antd';
import { useEffect } from 'react';
import { listRuns } from './api/simulation';
import { Workbench } from './features/workbench/Workbench';
import { useUiStore } from './stores/ui-store';

const { Content, Header, Footer } = Layout;

export default function App() {
  const runs = useQuery({
    queryKey: ['runs'], queryFn: ({ signal }) => listRuns(signal),
    refetchInterval: 10_000, refetchOnWindowFocus: true,
  });
  const runId = useUiStore((state) => state.selectedRunId);
  const selectRun = useUiStore((state) => state.selectRun);
  useEffect(() => {
    if (!runId && runs.data?.items[0]) selectRun(runs.data.items[0].run_id);
  }, [runs.data, runId, selectRun]);

  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <a className="brand" href="/">校园涌现<span>CAMPUS EMERGENCE</span></a>
        <Tag className="stage-tag">W1 · 通知与观察</Tag>
      </Header>
      <Content className="app-content">
        <div className="workspace-heading">
          <div>
            <Typography.Text className="eyebrow">多智能体仿真沙盒</Typography.Text>
            <h1>校园工作台</h1>
            <Typography.Paragraph type="secondary">发布一条活动通知，观察事件生效与角色记忆的形成。</Typography.Paragraph>
          </div>
          <div className="run-selector">
            <label className="field-label" htmlFor="run-select">选择运行</label>
            <Select id="run-select" aria-label="选择运行" value={runId} onChange={selectRun}
              loading={runs.isPending} placeholder="选择一个运行" style={{ width: '100%' }}
              options={runs.data?.items.map((run) => ({ value: run.run_id, label: `${run.name} · ${run.run_id}` }))} />
          </div>
        </div>
        {runs.isPending && <Spin description="正在读取运行列表…" />}
        {runs.isError && <Alert className="page-alert" type="error" showIcon title="暂时无法获取运行列表"
          description={runs.error.message} action={<Button onClick={() => void runs.refetch()}>重新连接</Button>} />}
        {!runs.isPending && !runs.isError && runs.data?.items.length === 0 && (
          <div className="empty-workspace"><Empty description={
            <Space orientation="vertical"><span>还没有可观察的运行</span>
              <Typography.Text type="secondary">请先按README执行开发初始化，再刷新运行列表。</Typography.Text>
              <Button onClick={() => void runs.refetch()}>刷新运行列表</Button>
            </Space>
          } /></div>
        )}
        {runId && <Workbench key={runId} runId={runId} />}
      </Content>
      <Footer className="app-footer">校园涌现 · 通知发布 → 事件生效 → 角色观察</Footer>
    </Layout>
  );
}
