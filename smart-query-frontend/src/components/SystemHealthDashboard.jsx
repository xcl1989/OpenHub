import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card, Row, Col, Statistic, Table, Tag, Spin, Empty, Button, Select, Typography, Tooltip,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, ThunderboltOutlined,
  ClockCircleOutlined, ApiOutlined, DatabaseOutlined, CloudServerOutlined,
  ReloadOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { adminService } from '../services/api';

const { Text } = Typography;

function StatusTag({ healthy, label }) {
  return (
    <Tag color={healthy ? 'green' : 'red'} style={{ fontSize: 13, padding: '2px 10px' }}>
      {healthy ? <CheckCircleOutlined /> : <CloseCircleOutlined />} {label}
    </Tag>
  );
}

function formatUptime(seconds) {
  if (!seconds) return '-';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}天${h}时`;
  if (h > 0) return `${h}时${m}分`;
  return `${m}分`;
}

function SystemHealthDashboard() {
  const [health, setHealth] = useState(null);
  const [performance, setPerformance] = useState(null);
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [perfHours, setPerfHours] = useState(24);
  const [countdown, setCountdown] = useState(30);
  const timerRef = useRef(null);
  const countdownRef = useRef(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [h, p, e] = await Promise.all([
        adminService.getSystemHealth(),
        adminService.getSystemPerformance(perfHours),
        adminService.getRecentErrors(20),
      ]);
      if (h.success) setHealth(h.data);
      if (p.success) setPerformance(p.data);
      if (e.success) setErrors(e.data || []);
    } catch {
    } finally {
      setLoading(false);
    }
  }, [perfHours]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      fetchData();
      setCountdown(30);
    }, 30000);
    countdownRef.current = setInterval(() => {
      setCountdown(prev => (prev > 0 ? prev - 1 : 30));
    }, 1000);
    return () => {
      clearInterval(timerRef.current);
      clearInterval(countdownRef.current);
    };
  }, [fetchData]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (loading && !health) return <Spin style={{ display: 'block', margin: '60px auto' }} />;

  const oc = health?.opencode || {};
  const mysql = health?.mysql || {};
  const redis = health?.redis || {};
  const sessions = health?.sessions || {};

  const perfColumns = [
    {
      title: '模型', dataIndex: 'model_id', key: 'model', ellipsis: true,
      render: t => <Text style={{ fontSize: 12 }}>{t}</Text>,
    },
    { title: '服务商', dataIndex: 'provider_id', key: 'provider', width: 100 },
    {
      title: '调用次数', dataIndex: 'count', key: 'count', width: 90,
      sorter: (a, b) => a.count - b.count,
    },
    {
      title: '平均(ms)', dataIndex: 'avg_ms', key: 'avg_ms', width: 90,
      sorter: (a, b) => a.avg_ms - b.avg_ms,
      render: v => <Text style={{ color: v > 30000 ? '#ff4d4f' : v > 10000 ? '#faad14' : '#52c41a' }}>{v.toLocaleString()}</Text>,
    },
    {
      title: '最大(ms)', dataIndex: 'max_ms', key: 'max_ms', width: 90,
      render: v => <Text style={{ color: v > 120000 ? '#ff4d4f' : '#666' }}>{v.toLocaleString()}</Text>,
    },
  ];

  const errorColumns = [
    { title: '时间', dataIndex: 'created_at', key: 'time', width: 150, render: t => t ? t.substring(5, 19) : '-' },
    { title: '用户', dataIndex: 'username', key: 'user', width: 80 },
    { title: '模型', dataIndex: 'model_id', key: 'model', ellipsis: true },
    {
      title: '耗时', dataIndex: 'duration_ms', key: 'duration', width: 90,
      render: v => <Text style={{ color: '#ff4d4f' }}>{(v / 1000).toFixed(1)}s</Text>,
    },
    { title: '问题预览', dataIndex: 'question_preview', key: 'q', ellipsis: true },
  ];

  return (
    <div style={{ padding: isMobile ? '0 4px' : 0 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          <ClockCircleOutlined /> {countdown}s 后自动刷新
        </Text>
        <Button size="small" icon={<ReloadOutlined />} onClick={() => { fetchData(); setCountdown(30); }}>
          刷新
        </Button>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: isMobile ? 16 : 24 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>opencode</Text>
              <StatusTag healthy={oc.status === 'healthy'} label={oc.status === 'healthy' ? '正常' : '异常'} />
            </div>
            <Statistic
              value={oc.latency_ms ?? '-'}
              suffix={oc.latency_ms ? 'ms' : ''}
              prefix={<CloudServerOutlined />}
              valueStyle={{ fontSize: isMobile ? 16 : 20, color: oc.latency_ms > 500 ? '#faad14' : undefined }}
            />
            {oc.version && <Text type="secondary" style={{ fontSize: 11 }}>v{oc.version}</Text>}
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>MySQL</Text>
              <StatusTag healthy={mysql.status === 'healthy'} label={mysql.status === 'healthy' ? '正常' : '异常'} />
            </div>
            <Statistic
              value={mysql.latency_ms ?? '-'}
              suffix={mysql.latency_ms ? 'ms' : ''}
              prefix={<DatabaseOutlined />}
              valueStyle={{ fontSize: isMobile ? 16 : 20 }}
            />
            {mysql.threads_connected != null && (
              <Text type="secondary" style={{ fontSize: 11 }}>连接: {mysql.threads_connected}</Text>
            )}
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>Redis</Text>
              <StatusTag healthy={redis.status === 'healthy'} label={redis.status === 'healthy' ? '正常' : '异常'} />
            </div>
            <Statistic
              value={redis.latency_ms ?? '-'}
              suffix={redis.latency_ms ? 'ms' : ''}
              prefix={<ApiOutlined />}
              valueStyle={{ fontSize: isMobile ? 16 : 20 }}
            />
            {redis.used_memory_mb != null && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                {redis.used_memory_mb}MB / {formatUptime(redis.uptime_seconds)}
              </Text>
            )}
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <div style={{ marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>活跃会话</Text>
            </div>
            <Statistic
              value={sessions.active_1h ?? 0}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ fontSize: isMobile ? 16 : 20 }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>
              处理中: {sessions.processing ?? 0}
            </Text>
          </Card>
        </Col>
      </Row>

      {performance && (
        <Card
          title={
            <span>
              <ThunderboltOutlined style={{ marginRight: 8 }} />
              性能概览
              <Select
                value={perfHours}
                onChange={setPerfHours}
                size="small"
                style={{ marginLeft: 12, width: 110 }}
              >
                <Select.Option value={1}>近 1 小时</Select.Option>
                <Select.Option value={6}>近 6 小时</Select.Option>
                <Select.Option value={24}>近 24 小时</Select.Option>
                <Select.Option value={72}>近 3 天</Select.Option>
              </Select>
            </span>
          }
          size="small"
          style={{ marginBottom: isMobile ? 16 : 24 }}
          styles={{ body: { padding: isMobile ? 8 : 12 } }}
        >
          <Row gutter={[12, 8]} style={{ marginBottom: 16 }}>
            <Col xs={8}>
              <Statistic title="总请求" value={performance.total_requests} valueStyle={{ fontSize: 16 }} />
            </Col>
            <Col xs={8}>
              <Statistic
                title="平均响应"
                value={performance.avg_response_ms}
                suffix="ms"
                valueStyle={{ fontSize: 16 }}
              />
            </Col>
            <Col xs={8}>
              <Tooltip title={`${performance.error_count} 个慢请求(>120s)`}>
                <Statistic
                  title="错误率"
                  value={performance.error_rate}
                  suffix="%"
                  valueStyle={{ fontSize: 16, color: performance.error_rate > 5 ? '#ff4d4f' : undefined }}
                  prefix={performance.error_rate > 5 ? <ExclamationCircleOutlined /> : undefined}
                />
              </Tooltip>
            </Col>
          </Row>
          {performance.by_model?.length > 0 ? (
            <Table
              dataSource={performance.by_model}
              columns={perfColumns}
              rowKey={r => `${r.model_id}|${r.provider_id}`}
              size="small"
              pagination={{ pageSize: 10 }}
              scroll={{ x: 500 }}
            />
          ) : (
            <Empty description="暂无性能数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>
      )}

      <Card
        title={<span><ExclamationCircleOutlined style={{ marginRight: 8 }} />慢请求记录 (&gt;120s)</span>}
        size="small"
        styles={{ body: { padding: isMobile ? 8 : 12 } }}
      >
        {errors.length > 0 ? (
          <Table
            dataSource={errors}
            columns={errorColumns}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 5 }}
            scroll={{ x: 500 }}
          />
        ) : (
          <Empty description="无慢请求记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>
    </div>
  );
}

export default SystemHealthDashboard;
