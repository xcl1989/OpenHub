import React, { useState, useEffect } from 'react';
import { Drawer, Table, Switch, Tag, Spin, message, Card, Typography, Button, Space, Input, Empty } from 'antd';
import {
  ThunderboltOutlined,
  SyncOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { skillService } from '../services/api';

const { Text, Title } = Typography;

function UserSkillManager({ open, onClose, isMobile }) {
  const width = isMobile ? '100%' : 720;
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    if (open) {
      fetchSkills();
    }
  }, [open]);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const result = await skillService.getSkills();
      if (result.success) {
        setSkills(result.data || []);
      } else {
        message.error(result.error || '获取技能列表失败');
      }
    } catch {
      message.error('获取技能列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (skillName, enabled) => {
    try {
      await skillService.updateSkill(skillName, enabled);
      setSkills(prev => prev.map(s =>
        s.skill_name === skillName
          ? { ...s, user_enabled: enabled, has_override: 1 }
          : s
      ));
      message.success(`${skillName} 已${enabled ? '启用' : '禁用'}`);
    } catch {
      message.error('更新失败');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await skillService.syncSkills();
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

  if (!open) return null;

  const filteredSkills = searchText
    ? skills.filter(s => s.skill_name.toLowerCase().includes(searchText.toLowerCase()))
    : skills;

  const enabledCount = skills.filter(s => s.user_enabled === true || (s.user_enabled === null && s.globally_enabled)).length;

  const getEnabledStatus = (record) => {
    if (record.has_override) {
      return record.user_enabled;
    }
    return record.globally_enabled === 1;
  };

  const columns = [
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
      key: 'enabled',
      width: 120,
      render: (_, record) => (
        <Switch
          checked={getEnabledStatus(record)}
          onChange={(val) => handleToggle(record.skill_name, val)}
          size="small"
        />
      ),
    },
    {
      title: '当前',
      key: 'status',
      width: 100,
      render: (_, record) => {
        const enabled = getEnabledStatus(record);
        if (record.has_override) {
          return enabled
            ? <Tag color="green">已启用</Tag>
            : <Tag color="red">已禁用</Tag>;
        }
        return enabled
          ? <Tag color="blue">默认</Tag>
          : <Tag color="default">默认</Tag>;
      },
    },
  ];

  return (
    <Drawer
      title={
        <Space>
          <ThunderboltOutlined />
          <span>技能管理</span>
        </Space>
      }
      placement="right"
      width={width}
      onClose={onClose}
      open={open}
      mask={false}
      extra={
        <Button size="small" icon={<SyncOutlined spin={syncing} />} onClick={handleSync} loading={syncing}>
          同步
        </Button>
      }
    >
      {loading ? (
        <Spin style={{ display: 'block', margin: '60px auto' }} />
      ) : (
        <>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Space>
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              <span>已启用：{enabledCount}/{skills.length}</span>
            </Space>
          </Card>

          <Input
            placeholder="搜索技能名称..."
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            allowClear
            style={{ width: 200, marginBottom: 12 }}
            size="small"
          />

          {filteredSkills.length === 0 ? (
            <Empty description="暂无可用技能，请点击同步按钮从工作空间加载" />
          ) : (
            <Table
              dataSource={filteredSkills}
              columns={columns}
              rowKey="skill_name"
              size="small"
              pagination={{ pageSize: 10 }}
            />
          )}
        </>
      )}
    </Drawer>
  );
}

export default UserSkillManager;