import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Select, Spin, Empty } from 'antd';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar,
} from 'recharts';
import { ThunderboltOutlined, UserOutlined, RobotOutlined, CalendarOutlined } from '@ant-design/icons';
import { adminService } from '../services/api';

const COLORS = ['#1890ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16'];

function UsageStats({ visible }) {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [days, setDays] = useState(30);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  useEffect(() => {
    if (!visible) return;
    fetchStats(days);
  }, [visible, days]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const fetchStats = async (d) => {
    setLoading(true);
    try {
      const result = await adminService.getUsageStats(d);
      if (result.success) setStats(result.data);
    } catch {} finally {
      setLoading(false);
    }
  };

  if (!visible) return null;
  if (loading) return <Spin style={{ display: 'block', margin: '60px auto' }} />;
  if (!stats) return <Empty description="暂无数据" />;

  const today = stats.daily?.length > 0 ? stats.daily[stats.daily.length - 1]?.count || 0 : 0;
  const activeUsers = stats.by_user?.length || 0;
  const topModel = stats.by_model?.length > 0 ? stats.by_model[0]?.model_id : '-';

  const modelColumns = [
    { title: '模型', dataIndex: 'model_id', key: 'model', ellipsis: true },
    { title: '服务商', dataIndex: 'provider_id', key: 'provider' },
    { title: '调用次数', dataIndex: 'count', key: 'count', sorter: (a, b) => a.count - b.count },
  ];

  const userColumns = [
    { title: '用户', dataIndex: 'username', key: 'username' },
    { title: '调用次数', dataIndex: 'count', key: 'count', sorter: (a, b) => a.count - b.count },
  ];

  return (
    <div style={{ padding: isMobile ? '0 4px' : 0 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: isMobile ? 'flex-start' : 'flex-end' }}>
        <Select value={days} onChange={setDays} style={{ width: isMobile ? '100%' : 120 }}>
          <Select.Option value={7}>近 7 天</Select.Option>
          <Select.Option value={30}>近 30 天</Select.Option>
          <Select.Option value={90}>近 90 天</Select.Option>
        </Select>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: isMobile ? 16 : 24 }}>
        <Col xs={12} sm={6}>
          <Card size="small"><Statistic title="总调用" value={stats.total} prefix={<ThunderboltOutlined />} valueStyle={{ fontSize: isMobile ? 16 : 20 }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small"><Statistic title="今日" value={today} prefix={<CalendarOutlined />} valueStyle={{ fontSize: isMobile ? 16 : 20 }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small"><Statistic title="活跃用户" value={activeUsers} prefix={<UserOutlined />} valueStyle={{ fontSize: isMobile ? 16 : 20 }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="热门模型"
              value={topModel}
              valueStyle={{ fontSize: isMobile ? 12 : 16 }}
              prefix={<RobotOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card title="每日调用趋势" style={{ marginBottom: isMobile ? 16 : 24 }} styles={{ body: { padding: isMobile ? 12 : 16 } }}>
        <ResponsiveContainer width="100%" height={isMobile ? 200 : 300}>
          <LineChart data={stats.daily || []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="count" stroke="#1890ff" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Row gutter={[12, 12]} style={{ marginBottom: isMobile ? 16 : 24 }}>
        <Col xs={24} md={12}>
          <Card title="模型使用分布" size="small" styles={{ body: { padding: isMobile ? 8 : 12 } }}>
            {stats.by_model?.length > 0 ? (
              <ResponsiveContainer width="100%" height={isMobile ? 200 : 300}>
                <PieChart>
                  <Pie
                    data={stats.by_model}
                    dataKey="count"
                    nameKey="model_id"
                    cx="50%"
                    cy="50%"
                    outerRadius={isMobile ? 70 : 100}
                    label={({ model_id, percent }) => `${model_id?.substring(0, 10)} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {stats.by_model.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : <Empty />}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="用户调用排行" size="small" styles={{ body: { padding: isMobile ? 8 : 12 } }}>
            {stats.by_user?.length > 0 ? (
              <ResponsiveContainer width="100%" height={isMobile ? 200 : 300}>
                <BarChart data={stats.by_user.slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="username" tick={{ fontSize: 11 }} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="count" fill="#1890ff" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Empty />}
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} md={12}>
          <Card title="模型调用明细" size="small" styles={{ body: { padding: isMobile ? 8 : 12 } }}>
            <Table dataSource={stats.by_model} columns={modelColumns} rowKey="model_id" size="small" pagination={{ pageSize: 5 }} scroll={{ x: 300 }} />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="用户调用明细" size="small" styles={{ body: { padding: isMobile ? 8 : 12 } }}>
            <Table dataSource={stats.by_user} columns={userColumns} rowKey="username" size="small" pagination={{ pageSize: 5 }} scroll={{ x: 300 }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default UsageStats;