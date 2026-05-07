import React, { useState, useEffect, useCallback } from 'react';
import { Drawer, Card, Row, Col, Statistic, Spin, Empty, Typography } from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
  ThunderboltOutlined, RobotOutlined,
} from '@ant-design/icons';
import { smartEntityService } from '../services/api';

const { Text } = Typography;

function EntityMetricsPanel({ open, onClose, entityId, entityName, isMobile }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchMetrics = useCallback(async () => {
    if (!entityId) return;
    setLoading(true);
    try {
      const res = await smartEntityService.getMetrics(entityId);
      if (res.ok) setMetrics(res.metrics);
    } catch {
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  useEffect(() => {
    if (open) fetchMetrics();
  }, [open, fetchMetrics]);

  return (
    <Drawer
      title={<span><RobotOutlined /> {entityName} - 数据看板</span>}
      placement="right"
      width={isMobile ? '100%' : 450}
      onClose={onClose}
      open={open}
      mask={false}
    >
      {loading ? (
        <Spin style={{ display: 'block', margin: '40px auto' }} />
      ) : !metrics ? (
        <Empty description="暂无数据" />
      ) : (
        <div>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card size="small">
                <Statistic
                  title="已接收任务"
                  value={metrics.total_tasks_received || 0}
                  prefix={<ThunderboltOutlined />}
                  valueStyle={{ fontSize: isMobile ? 18 : 22, color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small">
                <Statistic
                  title="成功完成"
                  value={metrics.total_tasks_completed || 0}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ fontSize: isMobile ? 18 : 22, color: '#52c41a' }}
                />
              </Card>
            </Col>
          </Row>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card size="small">
                <Statistic
                  title="失败任务"
                  value={metrics.total_tasks_failed || 0}
                  prefix={<CloseCircleOutlined />}
                  valueStyle={{ fontSize: isMobile ? 18 : 22, color: '#ff4d4f' }}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small">
                <Statistic
                  title="成功率"
                  value={
                    metrics.total_tasks_received > 0
                      ? Math.round((metrics.total_tasks_completed / metrics.total_tasks_received) * 100)
                      : 0
                  }
                  suffix="%"
                  valueStyle={{
                    fontSize: isMobile ? 18 : 22,
                    color: metrics.total_tasks_received > 0
                      ? (metrics.total_tasks_completed / metrics.total_tasks_received) > 0.8 ? '#52c41a' : '#faad14'
                      : '#999',
                  }}
                />
              </Card>
            </Col>
          </Row>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card size="small">
                <Statistic
                  title="平均响应"
                  value={metrics.avg_response_time || 0}
                  suffix="s"
                  prefix={<ClockCircleOutlined />}
                  valueStyle={{ fontSize: isMobile ? 18 : 22 }}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small">
                <Statistic
                  title="今日配额"
                  value={`${metrics.daily_used || 0} / ${metrics.daily_quota || 0}`}
                  valueStyle={{ fontSize: isMobile ? 16 : 18, color: (metrics.daily_used || 0) >= (metrics.daily_quota || 100) ? '#ff4d4f' : undefined }}
                />
              </Card>
            </Col>
          </Row>
          {metrics.last_task_at && (
            <Card size="small">
              <Text type="secondary" style={{ fontSize: 12 }}>
                最后活跃: {metrics.last_task_at}
              </Text>
            </Card>
          )}
        </div>
      )}
    </Drawer>
  );
}

export default EntityMetricsPanel;
