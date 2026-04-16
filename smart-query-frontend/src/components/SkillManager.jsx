import React, { useState, useEffect } from 'react';
import { Table, Switch, Tag, Spin, message, Card, Typography, Button, Space, Input } from 'antd';
import {
  ThunderboltOutlined,
  SyncOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { adminService } from '../services/api';

const { Text, Title } = Typography;

function SkillManager({ visible }) {
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  useEffect(() => {
    if (visible) fetchSkills();
  }, [visible]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const result = await adminService.getSkills();
      if (result.success) setSkills(result.data || []);
    } catch {
      message.error('获取技能列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (skillName, enabled) => {
    try {
      await adminService.updateSkill(skillName, enabled);
      setSkills(prev => prev.map(s => s.skill_name === skillName ? { ...s, globally_enabled: enabled ? 1 : 0 } : s));
      message.success(`${skillName} 已${enabled ? '启用' : '禁用'}`);
    } catch {
      message.error('更新失败');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await adminService.syncSkills();
      if (result.success) {
        message.success(result.message || '同步成功');
        fetchSkills();
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

  const filteredSkills = searchText
    ? skills.filter(s => s.skill_name.toLowerCase().includes(searchText.toLowerCase()))
    : skills;

  const enabledCount = skills.filter(s => s.globally_enabled === 1).length;

  const mobileColumns = [
    {
      title: '技能',
      dataIndex: 'skill_name',
      key: 'skill_name',
      width: 120,
      render: (name) => <Tag color="blue" style={{ fontSize: 12 }}>{name}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'globally_enabled',
      key: 'enabled',
      width: 80,
      render: (enabled, record) => (
        <Switch
          checked={enabled === 1}
          onChange={(val) => handleToggle(record.skill_name, val)}
          size="small"
        />
      ),
    },
  ];

  const desktopColumns = [
    {
      title: '技能',
      dataIndex: 'skill_name',
      key: 'skill_name',
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
      title: '状态',
      dataIndex: 'globally_enabled',
      key: 'enabled',
      width: 100,
      render: (enabled, record) => (
        <Switch
          checked={enabled === 1}
          onChange={(val) => handleToggle(record.skill_name, val)}
          size="small"
        />
      ),
    },
    {
      title: '当前',
      key: 'status',
      width: 80,
      render: (_, record) => (
        record.globally_enabled === 1
          ? <Tag color="green">启用</Tag>
          : <Tag color="red">禁用</Tag>
      ),
    },
  ];

  const columns = isMobile ? mobileColumns : desktopColumns;

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
        <Title level={isMobile ? 5 : 4} style={{ margin: 0 }}>全局技能管理</Title>
        <Space size="small" wrap={isMobile}>
          <Button
            size={isMobile ? 'small' : 'small'}
            icon={<SyncOutlined spin={syncing} />}
            onClick={handleSync}
            loading={syncing}
          >
            {isMobile ? '同步' : '从工作空间同步'}
          </Button>
          <Button size={isMobile ? 'small' : 'small'} onClick={fetchSkills}>
            刷新
          </Button>
        </Space>
      </div>

      <Card size="small" style={{ marginBottom: 12 }} styles={{ body: { padding: '8px 12px' } }}>
        <Space>
          <CheckCircleOutlined style={{ color: '#52c41a' }} />
          <span style={{ fontSize: isMobile ? 12 : 14 }}>已启用：{enabledCount}/{skills.length}</span>
        </Space>
      </Card>

      <div style={{ marginBottom: 12 }}>
        <Input
          placeholder="搜索技能..."
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          allowClear
          style={{ width: '100%' }}
          size="small"
        />
      </div>

      <Table
        dataSource={filteredSkills}
        columns={columns}
        rowKey="skill_name"
        size="small"
        pagination={{ pageSize: isMobile ? 10 : 15 }}
        scroll={{ x: isMobile ? 200 : undefined }}
      />
    </div>
  );
}

export default SkillManager;