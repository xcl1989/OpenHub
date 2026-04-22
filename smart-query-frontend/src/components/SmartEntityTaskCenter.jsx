import React, { useState, useEffect } from 'react';
import { Drawer, Tabs, Card, Tag, Button, Badge, Empty, Spin, message, Space, Timeline, Typography } from 'antd';
import {
  TeamOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  SendOutlined,
  InboxOutlined
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { smartEntityTaskService } from '../services/api';

const { Text } = Typography;

function SmartEntityTaskCenter({ open, onClose, isMobile }) {
  const width = isMobile ? '100%' : 720;
  const [loading, setLoading] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [activeTab, setActiveTab] = useState('pending');

  useEffect(() => {
    if (open) {
      fetchTasks();
    }
  }, [open, activeTab]);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const result = await smartEntityTaskService.list({ status: activeTab === 'all' ? undefined : activeTab });
      setTasks(result.tasks || []);
    } catch {
      message.error('获取任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (taskId, action, reason = null) => {
    try {
      await smartEntityTaskService.action(taskId, action, reason);
      message.success(action === 'accept' ? '已接受任务' : action === 'reject' ? '已拒绝任务' : '已取消任务');
      fetchTasks();
    } catch (err) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const getStatusTag = (status) => {
    const statusMap = {
      pending: { color: 'gold', icon: <ClockCircleOutlined />, text: '待处理' },
      accepted: { color: 'blue', icon: <CheckCircleOutlined />, text: '已接受' },
      processing: { color: 'processing', icon: <SyncOutlined spin />, text: '进行中' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      rejected: { color: 'error', icon: <CloseCircleOutlined />, text: '已拒绝' },
      timeout: { color: 'default', icon: <ClockCircleOutlined />, text: '已超时' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
    };
    const config = statusMap[status] || { color: 'default', text: status };
    return <Tag icon={config.icon} color={config.color}>{config.text}</Tag>;
  };

  const renderTaskCard = (task) => {
    const isIncoming = task.to_user_id === JSON.parse(localStorage.getItem('user') || '{}').id;
    
    return (
      <Card 
        key={task.task_id} 
        size="small" 
        style={{ marginBottom: 12 }}
        title={
          <Space>
            {isIncoming ? <InboxOutlined /> : <SendOutlined />}
            <span>{task.task_title}</span>
            {getStatusTag(task.status)}
          </Space>
        }
        extra={
          <Space>
            <span style={{ color: '#999', fontSize: 12 }}>
              {new Date(task.created_at).toLocaleString()}
            </span>
            {task.status === 'pending' && isIncoming && (
              <>
                <Button type="primary" size="small" onClick={() => handleAction(task.task_id, 'accept')}>
                  接受
                </Button>
                <Button size="small" danger onClick={() => handleAction(task.task_id, 'reject')}>
                  拒绝
                </Button>
              </>
            )}
          </Space>
        }
      >
        <p style={{ color: '#666', fontSize: 13 }}>{task.task_description}</p>
        <Space size="small" wrap>
          <Tag>委托人: {task.from_username}</Tag>
          <Tag>被委托人: {task.to_username}</Tag>
          <Tag>执行智能体: {task.to_entity_name}</Tag>
          <Tag>类型: {task.task_type_name || task.task_type}</Tag>
        </Space>
        {task.status === 'pending' && !isIncoming && (
          <div style={{ marginTop: 8 }}>
            <Button size="small" onClick={() => handleAction(task.task_id, 'cancel')}>
              取消任务
            </Button>
          </div>
        )}

        {task.status === 'completed' && task.output_data?.result && (
          <div style={{ marginTop: 12, padding: '8px 12px', background: '#f6ffed', borderRadius: 4, border: '1px solid #b7eb8f' }}>
            <Text strong style={{ color: '#52c41a' }}>执行结果：</Text>
            <div className="markdown-content" style={{ marginTop: 8, fontSize: 13 }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.output_data.result}</ReactMarkdown>
            </div>
          </div>
        )}

        {task.status === 'failed' && task.error_message && (
          <div style={{ marginTop: 12, padding: 12, background: '#fff2f0', borderRadius: 4, border: '1px solid #ffccc7' }}>
            <Text strong style={{ color: '#ff4d4f' }}>失败原因：</Text>
            <div style={{ marginTop: 8, fontSize: 13, color: '#333' }}>
              {task.error_message}
            </div>
          </div>
        )}
      </Card>
    );
  };

  const getTabContent = (status, emptyText) => {
    if (loading) return <Spin style={{ display: 'block', margin: '40px auto' }} />;
    if (tasks.length === 0) return <Empty description={emptyText} />;
    return (
      <Timeline items={tasks.map(task => ({
        key: task.task_id,
        children: renderTaskCard(task)
      }))} />
    );
  };

  const tabItems = [
    {
      key: 'pending',
      label: <Badge count={tasks.filter(t => t.status === 'pending').length} offset={[10, 0]}>待处理</Badge>,
      children: getTabContent('pending', '暂无待处理任务')
    },
    {
      key: 'processing',
      label: '进行中',
      children: getTabContent('processing', '暂无进行中的任务')
    },
    {
      key: 'completed',
      label: '已完成',
      children: getTabContent('completed', '暂无已完成任务')
    },
    {
      key: 'all',
      label: '全部',
      children: getTabContent('all', '暂无任务')
    }
  ];

  return (
    <Drawer
      title={<div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><TeamOutlined /><span>协作任务中心</span></div>}
      placement="right"
      width={width}
      onClose={onClose}
      open={open}
      mask={false}
    >
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </Drawer>
  );
}

export default SmartEntityTaskCenter;
