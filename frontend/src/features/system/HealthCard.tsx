import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Descriptions, Space, Spin, Tag, Typography } from 'antd';
import { getReadiness } from '../../api/health';
import { useUiStore } from '../../stores/ui-store';

const { Text } = Typography;

export function HealthCard() {
  const showDetails = useUiStore((state) => state.showConnectionDetails);
  const toggleDetails = useUiStore((state) => state.toggleConnectionDetails);
  const readiness = useQuery({
    queryKey: ['system', 'readiness'],
    queryFn: ({ signal }) => getReadiness(signal),
    refetchInterval: 15_000,
  });

  return (
    <Card
      title="环境连接"
      extra={
        <Button onClick={() => void readiness.refetch()} loading={readiness.isFetching}>
          重新检查
        </Button>
      }
    >
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        {readiness.isPending && <Spin description="正在检查 API 与依赖服务…" />}
        {readiness.isError && (
          <Alert
            type="error"
            showIcon
            title="暂时无法获取环境状态"
            description={readiness.error.message}
          />
        )}
        {readiness.data && !readiness.isError && (
          <>
            <Alert
              type={readiness.data.status === 'ready' ? 'success' : 'warning'}
              showIcon
              title={
                readiness.data.status === 'ready'
                  ? 'API、PostgreSQL 与 Redis 已就绪'
                  : 'API 已响应，部分依赖尚未就绪'
              }
            />
            <Descriptions column={1} size="small">
              <Descriptions.Item label="PostgreSQL">
                <Tag color={readiness.data.dependencies.postgres === 'ok' ? 'green' : 'orange'}>
                  {readiness.data.dependencies.postgres === 'ok' ? '可连接' : '不可用'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Redis">
                <Tag color={readiness.data.dependencies.redis === 'ok' ? 'green' : 'orange'}>
                  {readiness.data.dependencies.redis === 'ok' ? '可连接' : '不可用'}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
          </>
        )}
        <Button type="link" onClick={toggleDetails} style={{ paddingInline: 0 }}>
          {showDetails ? '收起连接详情' : '查看连接详情'}
        </Button>
        {showDetails && (
          <Text type="secondary">
            当前检查接口：<Text code>/api/health/ready</Text>，每15秒刷新。
            此检查仅验证API及数据依赖连接；通知处理结果以工作台的权威事件为准。
          </Text>
        )}
      </Space>
    </Card>
  );
}
