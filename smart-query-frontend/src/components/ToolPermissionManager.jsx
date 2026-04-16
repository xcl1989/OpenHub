import React, { useState, useEffect } from 'react';
import { Table, Select, Tag, Spin, message, Card, Row, Col, Typography, Button, Space } from 'antd';
import {
  SafetyCertificateOutlined,
  LockOutlined,
  QuestionCircleOutlined,
  CheckCircleOutlined,
  StopOutlined,
  SyncOutlined,
  ScheduleOutlined,
} from '@ant-design/icons';
import { adminService } from '../services/api';

const { Text, Title } = Typography;

const RISK_CONFIG = {
  dangerous: { color: '#ff4d4f', label: '危险', icon: <LockOutlined /> },
  moderate: { color: '#faad14', label: '敏感', icon: <QuestionCircleOutlined /> },
  safe: { color: '#52c41a', label: '安全', icon: <CheckCircleOutlined /> },
  custom: { color: '#1890ff', label: '自定义', icon: <ScheduleOutlined /> },
};

const ACTION_OPTIONS = [
  { value: 'deny', label: '拒绝', color: '#ff4d4f', icon: <StopOutlined /> },
  { value: 'ask', label: '审批', color: '#faad14', icon: <QuestionCircleOutlined /> },
  { value: 'allow', label: '允许', color: '#52c41a', icon: <CheckCircleOutlined /> },
];

const ACTION_CONFIG = {
  deny: { color: '#ff4d4f', label: '拒绝', icon: <StopOutlined /> },
  ask: { color: '#faad14', label: '审批', icon: <QuestionCircleOutlined /> },
  allow: { color: '#52c41a', label: '允许', icon: <CheckCircleOutlined /> },
};

function ToolPermissionManager({ visible }) {
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  useEffect(() => {
    if (visible) fetchTools();
  }, [visible]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const fetchTools = async () => {
    setLoading(true);
    try {
      const result = await adminService.getTools();
      if (result.success) setTools(result.data || []);
    } catch {
      message.error('获取工具列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleActionChange = async (toolName, action) => {
    try {
      await adminService.updateTool(toolName, action);
      setTools(prev => prev.map(t => t.tool_name === toolName ? { ...t, global_action: action } : t));
      message.success(`${toolName} 已设置为 ${ACTION_CONFIG[action]?.label}`);
    } catch {
      message.error('更新失败');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await adminService.syncToolsConfig();
      if (result.success) {
        message.success(result.message || '同步成功');
      } else {
        message.error(result.error || '同步失败');
      }
    } catch {
      message.error('同步失败');
    } finally {
      setSyncing(false);
    }
  };

  if (!visible) return null;
  if (loading) return <Spin style={{ display: 'block', margin: '60px auto' }} />;

  const dangerousTools = tools.filter(t => t.risk_level === 'dangerous');
  const moderateTools = tools.filter(t => t.risk_level === 'moderate');
  const safeTools = tools.filter(t => t.risk_level === 'safe');
  const customTools = tools.filter(t => t.risk_level === 'custom');

  const mobileColumns = [
    {
      title: '工具',
      dataIndex: 'tool_name',
      key: 'tool_name',
      width: 120,
      render: (name) => <Tag color="blue" style={{ fontSize: 12 }}>{name}</Tag>,
    },
    {
      title: '权限',
      dataIndex: 'global_action',
      key: 'global_action',
      width: 100,
      render: (action, record) => (
        <Select
          value={action || 'allow'}
          onChange={(val) => handleActionChange(record.tool_name, val)}
          size="small"
          style={{ width: 80 }}
        >
          {ACTION_OPTIONS.map(opt => (
            <Select.Option key={opt.value} value={opt.value}>
              <span style={{ color: opt.color, fontSize: 12 }}>{opt.label}</span>
            </Select.Option>
          ))}
        </Select>
      ),
    },
  ];

  const desktopColumns = [
    {
      title: '工具',
      dataIndex: 'tool_name',
      key: 'tool_name',
      width: 180,
      render: (name) => <Tag color="blue">{name}</Tag>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '全局权限',
      dataIndex: 'global_action',
      key: 'global_action',
      width: 160,
      render: (action, record) => (
        <Select
          value={action || 'allow'}
          onChange={(val) => handleActionChange(record.tool_name, val)}
          size="small"
          style={{ width: 100 }}
        >
          {ACTION_OPTIONS.map(opt => (
            <Select.Option key={opt.value} value={opt.value}>
              <Space size={4}>
                <span style={{ color: opt.color }}>{opt.icon}</span>
                <span>{opt.label}</span>
              </Space>
            </Select.Option>
          ))}
        </Select>
      ),
    },
    {
      title: '当前',
      dataIndex: 'global_action',
      key: 'status',
      width: 80,
      render: (action) => {
        const cfg = ACTION_CONFIG[action] || ACTION_CONFIG.allow;
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
  ];

  const renderToolTable = (toolList, title, titleIcon) => {
    const columns = isMobile ? mobileColumns : desktopColumns;
    return (
      <Card title={<Space>{titleIcon} {title}</Space>} size="small" style={{ marginBottom: isMobile ? 12 : 16 }} styles={{ body: { padding: isMobile ? 8 : 12 } }}>
        {toolList.length === 0 ? (
          <Text type="secondary">暂无工具</Text>
        ) : (
          <Table
            dataSource={toolList}
            columns={columns}
            rowKey="tool_name"
            size="small"
            pagination={false}
            scroll={{ x: isMobile ? 220 : undefined }}
          />
        )}
      </Card>
    );
  };

  return (
    <div style={{ padding: isMobile ? '0 4px' : 0 }}>
      <div style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: 'space-between',
        alignItems: isMobile ? 'flex-start' : 'center',
        marginBottom: 16,
        gap: isMobile ? 8 : 0
      }}>
        <Title level={isMobile ? 5 : 4} style={{ margin: 0 }}>全局工具权限</Title>
        <Space size={isMobile ? 'small' : 'small'} wrap={isMobile}>
          <Button
            size={isMobile ? 'small' : 'small'}
            icon={<SyncOutlined spin={syncing} />}
            onClick={handleSync}
            loading={syncing}
          >
            {isMobile ? '同步' : '同步到 opencode'}
          </Button>
          <Button size={isMobile ? 'small' : 'small'} onClick={fetchTools}>
            刷新
          </Button>
        </Space>
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small" styles={{ body: { padding: '8px 12px' } }}>
            <Space>
              <StopOutlined style={{ color: '#ff4d4f' }} />
              <span style={{ fontSize: isMobile ? 12 : 14 }}>危险：{dangerousTools.length}</span>
            </Space>
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" styles={{ body: { padding: '8px 12px' } }}>
            <Space>
              <QuestionCircleOutlined style={{ color: '#faad14' }} />
              <span style={{ fontSize: isMobile ? 12 : 14 }}>敏感：{moderateTools.length}</span>
            </Space>
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" styles={{ body: { padding: '8px 12px' } }}>
            <Space>
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              <span style={{ fontSize: isMobile ? 12 : 14 }}>安全：{safeTools.length}</span>
            </Space>
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" styles={{ body: { padding: '8px 12px' } }}>
            <Space>
              <ScheduleOutlined style={{ color: '#1890ff' }} />
              <span style={{ fontSize: isMobile ? 12 : 14 }}>自定义：{customTools.length}</span>
            </Space>
          </Card>
        </Col>
      </Row>

      {customTools.length > 0 && renderToolTable(
        customTools,
        '自定义工具（定时任务等扩展功能）',
        <ScheduleOutlined style={{ color: '#1890ff' }} />
      )}
      {dangerousTools.length > 0 && renderToolTable(
        dangerousTools,
        '危险工具（建议拒绝）',
        <StopOutlined style={{ color: '#ff4d4f' }} />
      )}
      {moderateTools.length > 0 && renderToolTable(
        moderateTools,
        '敏感工具（建议审批）',
        <QuestionCircleOutlined style={{ color: '#faad14' }} />
      )}
      {safeTools.length > 0 && renderToolTable(
        safeTools,
        '安全工具',
        <CheckCircleOutlined style={{ color: '#52c41a' }} />
      )}
    </div>
  );
}

export default ToolPermissionManager;