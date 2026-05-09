import React, { useState, useEffect } from 'react';
import { Drawer, Table, Switch, Tag, Spin, message, Card, Space, Input, Button, Form, Select, Popconfirm } from 'antd';
import { ClockCircleOutlined, PlayCircleOutlined, EditOutlined, CloseOutlined, CheckOutlined, BellOutlined } from '@ant-design/icons';
import { taskService, channelService } from '../services/api';

function TaskManager({ open, onClose, isMobile }) {
  const width = isMobile ? '100%' : 720;
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedRowKey, setExpandedRowKey] = useState(null);
  const [editingTask, setEditingTask] = useState(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [runningTaskId, setRunningTaskId] = useState(null);
  const [userChannels, setUserChannels] = useState([]);

  useEffect(() => {
    if (open) {
      fetchTasks();
      fetchUserChannels();
    }
  }, [open]);

  const fetchUserChannels = async () => {
    try {
      const result = await channelService.getUserBindingsWithChannel();
      if (result.success) {
        setUserChannels(result.data || []);
      }
    } catch {}
  };

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const result = await taskService.getTasks();
      if (result.ok) {
        setTasks(result.tasks || []);
      } else {
        message.error('获取任务列表失败');
      }
    } catch {
      message.error('获取任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (taskId, currentEnabled) => {
    try {
      const result = await taskService.toggleTask(taskId);
      if (result.ok) {
        setTasks(prev => prev.map(t =>
          t.id === taskId ? { ...t, enabled: result.enabled } : t
        ));
        message.success(result.enabled ? '任务已启用' : '任务已暂停');
      }
    } catch {
      message.error('操作失败');
    }
  };

  const handleRun = async (taskId) => {
    setRunningTaskId(taskId);
    try {
      const result = await taskService.runTask(taskId);
      if (result.ok) {
        message.success('任务已触发');
      }
    } catch {
      message.error('触发失败');
    } finally {
      setRunningTaskId(null);
    }
  };

  const handleExpand = (task) => {
    if (expandedRowKey === task.id) {
      setExpandedRowKey(null);
      setEditingTask(null);
      form.resetFields();
    } else {
      setExpandedRowKey(task.id);
      setEditingTask({ ...task });
      form.setFieldsValue({
        name: task.name,
        question: task.question,
        cron_expression: task.cron_expression,
        notify_channel_id: task.notify_channel_id,
      });
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const result = await taskService.updateTask(editingTask.id, values);
      if (result.ok) {
        setTasks(prev => prev.map(t =>
          t.id === editingTask.id ? { ...t, ...values } : t
        ));
        setExpandedRowKey(null);
        setEditingTask(null);
        form.resetFields();
        message.success('保存成功');
      }
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setExpandedRowKey(null);
    setEditingTask(null);
    form.resetFields();
  };

  const enabledCount = tasks.filter(t => t.enabled).length;

  const columns = [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      width: 160,
      render: (name, record) => (
        <Space>
          <Tag color={record.enabled ? 'green' : 'default'}>
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            {name}
          </Tag>
        </Space>
      ),
    },
    {
      title: '任务内容',
      dataIndex: 'question',
      key: 'question',
      ellipsis: true,
      render: (q) => <span style={{ color: '#666' }}>{q}</span>,
    },
    {
      title: '执行周期',
      dataIndex: 'cron_expression',
      key: 'cron_expression',
      width: 130,
      render: (cron) => <Tag color="blue">{cron}</Tag>,
    },
    {
      title: '通知',
      dataIndex: 'notify_channel_id',
      key: 'notify_channel_id',
      width: 70,
      render: (channelId) => channelId ? <BellOutlined style={{ color: '#1890ff' }} /> : <span style={{ color: '#ccc' }}>-</span>,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          onChange={() => handleToggle(record.id, enabled)}
          size="small"
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<PlayCircleOutlined />}
            loading={runningTaskId === record.id}
            onClick={() => handleRun(record.id)}
            title="立即执行"
          />
          <Button
            type="text"
            size="small"
            icon={expandedRowKey === record.id ? <CloseOutlined /> : <EditOutlined />}
            onClick={() => handleExpand(record)}
            title={expandedRowKey === record.id ? '取消编辑' : '编辑'}
          />
        </Space>
      ),
    },
  ];

  const expandedRowRender = (task) => {
    if (expandedRowKey !== task.id) return null;
    return (
      <Card size="small" style={{ background: '#fafafa', margin: '8px 0' }}>
        <Form form={form} layout="vertical" size="small">
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <Space wrap>
              <Form.Item
                name="name"
                label="任务名称"
                rules={[{ required: true, message: '请输入任务名称' }]}
                style={{ marginBottom: 0 }}
              >
                <Input placeholder="任务名称" style={{ width: 200 }} />
              </Form.Item>
              <Form.Item
                name="cron_expression"
                label="执行周期"
                rules={[
                  { required: true, message: '请输入 cron 表达式' },
                  {
                    pattern: /^\S+\s+\S+\s+\S+\s+\S+\s+\S+$/,
                    message: '必须是 5 字段 cron（分 时 日 月 周），例如：0 9 * * *',
                  },
                ]}
                style={{ marginBottom: 0 }}
              >
                <Input placeholder="0 9 * * *" style={{ width: 160 }} />
              </Form.Item>
            </Space>
            <Form.Item
              name="notify_channel_id"
              label="通知渠道"
              style={{ marginBottom: 8 }}
            >
              <Select
                placeholder="不通知"
                allowClear
                style={{ width: '100%' }}
                suffixIcon={<BellOutlined />}
              >
                {userChannels.map(ch => (
                  <Select.Option key={ch.channel_id} value={ch.channel_id}>
                    <Space>
                      <Tag color="blue" style={{ marginRight: 0 }}>{ch.channel_type}</Tag>
                      {ch.channel_name}
                      {!ch.has_chat_id && <span style={{ color: '#999', fontSize: 12 }}>(未关联会话)</span>}
                    </Space>
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
            <Form.Item
              name="question"
              label="任务内容"
              rules={[{ required: true, message: '请输入任务内容' }]}
              style={{ marginBottom: 8 }}
            >
              <Input.TextArea
                placeholder="任务内容..."
                rows={2}
                style={{ width: '100%' }}
              />
            </Form.Item>
            <Space>
              <Button
                type="primary"
                size="small"
                icon={<CheckOutlined />}
                onClick={handleSave}
                loading={saving}
              >
                保存
              </Button>
              <Button size="small" onClick={handleCancel}>
                取消
              </Button>
            </Space>
          </Space>
        </Form>
      </Card>
    );
  };

  if (!open) return null;

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ClockCircleOutlined />
          <span>任务管理</span>
        </div>
      }
      placement="right"
      width={width}
      onClose={onClose}
      open={open}
      mask={false}
    >
      {loading ? (
        <Spin style={{ display: 'block', margin: '60px auto' }} />
      ) : (
        <>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Space>
              <CheckOutlined style={{ color: '#52c41a' }} />
              <span>已启用：{enabledCount}/{tasks.length}</span>
            </Space>
          </Card>

          {tasks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
              暂无定时任务
            </div>
          ) : (
            <Table
              dataSource={tasks}
              columns={columns}
              rowKey="id"
              size="small"
              pagination={{ pageSize: 10 }}
              expandable={{
                expandedRowRender,
                expandedRowKeys: expandedRowKey ? [expandedRowKey] : [],
                showExpandColumn: false,
              }}
            />
          )}
        </>
      )}
    </Drawer>
  );
}

export default TaskManager;
