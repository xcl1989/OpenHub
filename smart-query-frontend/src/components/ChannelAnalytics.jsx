import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Row, Col, Statistic, Table, Select, Spin, Empty, Typography,
} from 'antd';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Legend,
} from 'recharts';
import {
  SendOutlined, ApiOutlined, TeamOutlined, WarningOutlined,
} from '@ant-design/icons';
import { adminService, channelService } from '../services/api';

const { Text } = Typography;

const CHANNEL_TYPE_MAP = { feishu: '飞书', wecom: '企业微信', dingtalk: '钉钉' };

function ChannelAnalytics() {
  const [loading, setLoading] = useState(false);
  const [analytics, setAnalytics] = useState(null);
  const [days, setDays] = useState(30);
  const [channelId, setChannelId] = useState(null);
  const [channels, setChannels] = useState([]);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  const fetchChannels = useCallback(async () => {
    try {
      const res = await channelService.listChannels();
      if (res.success) setChannels(res.data || []);
    } catch {}
  }, []);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminService.getChannelAnalytics(days, channelId);
      if (res.success) setAnalytics(res.data);
    } catch {
    } finally {
      setLoading(false);
    }
  }, [days, channelId]);

  useEffect(() => {
    fetchChannels();
  }, [fetchChannels]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (loading && !analytics) return <Spin style={{ display: 'block', margin: '60px auto' }} />;

  const channelColumns = [
    {
      title: '渠道名称', dataIndex: 'name', key: 'name', ellipsis: true,
    },
    {
      title: '类型', dataIndex: 'channel_type', key: 'type', width: 80,
      render: t => CHANNEL_TYPE_MAP[t] || t,
    },
    {
      title: '总消息', dataIndex: 'total_msgs', key: 'total', width: 80,
      sorter: (a, b) => a.total_msgs - b.total_msgs,
    },
    {
      title: '入站', dataIndex: 'inbound_count', key: 'inbound', width: 70,
    },
    {
      title: '出站', dataIndex: 'outbound_count', key: 'outbound', width: 70,
    },
    {
      title: '失败', dataIndex: 'failed_count', key: 'failed', width: 60,
      render: v => <Text style={{ color: v > 0 ? '#ff4d4f' : '#999' }}>{v}</Text>,
    },
    {
      title: '错误率', dataIndex: 'error_rate', key: 'err_rate', width: 80,
      render: v => (
        <Text style={{ color: v > 5 ? '#ff4d4f' : v > 0 ? '#faad14' : '#52c41a' }}>
          {v}%
        </Text>
      ),
      sorter: (a, b) => a.error_rate - b.error_rate,
    },
  ];

  return (
    <div style={{ padding: isMobile ? '0 4px' : 0 }}>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Select value={days} onChange={setDays} style={{ width: 120 }}>
          <Select.Option value={7}>近 7 天</Select.Option>
          <Select.Option value={30}>近 30 天</Select.Option>
          <Select.Option value={90}>近 90 天</Select.Option>
        </Select>
        <Select
          value={channelId}
          onChange={setChannelId}
          style={{ width: 180 }}
          allowClear
          placeholder="全部渠道"
        >
          {channels.map(c => (
            <Select.Option key={c.id} value={c.id}>
              {c.name} ({CHANNEL_TYPE_MAP[c.channel_type] || c.channel_type})
            </Select.Option>
          ))}
        </Select>
      </div>

      {analytics && (
        <>
          <Row gutter={[12, 12]} style={{ marginBottom: isMobile ? 16 : 24 }}>
            <Col xs={12} sm={6}>
              <Card size="small">
                <Statistic
                  title="总消息量"
                  value={analytics.total_messages}
                  prefix={<SendOutlined />}
                  valueStyle={{ fontSize: isMobile ? 16 : 20 }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small">
                <Statistic
                  title="活跃绑定"
                  value={analytics.active_bindings}
                  prefix={<TeamOutlined />}
                  valueStyle={{ fontSize: isMobile ? 16 : 20 }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small">
                <Statistic
                  title="入/出站比"
                  value={
                    analytics.daily?.length > 0
                      ? (() => {
                          const totalIn = analytics.daily.reduce((s, d) => s + d.inbound, 0);
                          const totalOut = analytics.daily.reduce((s, d) => s + d.outbound, 0);
                          return `${totalIn} / ${totalOut}`;
                        })()
                      : '0 / 0'
                  }
                  prefix={<ApiOutlined />}
                  valueStyle={{ fontSize: isMobile ? 14 : 16 }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small">
                <Statistic
                  title="错误率"
                  value={analytics.error_rate}
                  suffix="%"
                  prefix={analytics.error_rate > 5 ? <WarningOutlined /> : undefined}
                  valueStyle={{
                    fontSize: isMobile ? 16 : 20,
                    color: analytics.error_rate > 5 ? '#ff4d4f' : undefined,
                  }}
                />
              </Card>
            </Col>
          </Row>

          <Card
            title="每日消息趋势"
            size="small"
            style={{ marginBottom: isMobile ? 16 : 24 }}
            styles={{ body: { padding: isMobile ? 12 : 16 } }}
          >
            {analytics.daily?.length > 0 ? (
              <ResponsiveContainer width="100%" height={isMobile ? 220 : 300}>
                <LineChart data={analytics.daily}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="inbound" stroke="#1890ff" strokeWidth={2} name="入站" dot={{ r: 2 }} />
                  <Line type="monotone" dataKey="outbound" stroke="#52c41a" strokeWidth={2} name="出站" dot={{ r: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>

          {analytics.by_channel?.length > 0 && (
            <Card
              title="渠道对比"
              size="small"
              styles={{ body: { padding: isMobile ? 8 : 12 } }}
            >
              <Table
                dataSource={analytics.by_channel}
                columns={channelColumns}
                rowKey="channel_id"
                size="small"
                pagination={{ pageSize: 10 }}
                scroll={{ x: 500 }}
              />
            </Card>
          )}
        </>
      )}

      {!analytics && !loading && <Empty description="暂无渠道数据" />}
    </div>
  );
}

export default ChannelAnalytics;
