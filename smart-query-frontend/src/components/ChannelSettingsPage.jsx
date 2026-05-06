import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Button, Modal, Form, Input, Select, Space, Table, Tag, message,
  Typography, Popconfirm, Alert, Descriptions, Spin, Divider,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, ReloadOutlined, SendOutlined,
  ApiOutlined, CheckCircleOutlined, CloseCircleOutlined, LinkOutlined,
} from '@ant-design/icons';
import { channelService, adminService } from '../services/api';

const { Title, Text } = Typography;
const { Option } = Select;

function FeishuConfigForm({ form, models }) {
  return (
    <>
      <Form.Item name="app_id" label="App ID" rules={[{ required: true, message: '请输入飞书 App ID' }]}>
        <Input placeholder="cli_xxxxxxxxxxxxxxxx" />
      </Form.Item>
      <Form.Item name="app_secret" label="App Secret" rules={[{ required: true, message: '请输入飞书 App Secret' }]}>
        <Input.Password placeholder="飞书应用密钥" />
      </Form.Item>
      <Form.Item name="verify_token" label="Verification Token">
        <Input placeholder="事件订阅验证令牌（可选）" />
      </Form.Item>
      <Form.Item name="encrypt_key" label="Encrypt Key">
        <Input placeholder="加密密钥（可选）" />
      </Form.Item>
      <Form.Item name="bot_name" label="机器人名称">
        <Input placeholder="OpenHub" />
      </Form.Item>
      <Form.Item name="model" label="默认模型">
        <Select placeholder="留空则使用全局默认模型" allowClear showSearch optionFilterProp="label" loading={!models}>
          {(models || []).map(m => (
            <Option key={`${m.providerID}|${m.modelID}`} value={`${m.providerID}|${m.modelID}`} label={`${m.name || m.modelID}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{m.name || m.modelID}</span>
                <Text type="secondary" style={{ fontSize: 11 }}>{m.providerName || m.providerID}</Text>
              </div>
            </Option>
          ))}
        </Select>
      </Form.Item>
    </>
  );
}

export default function ChannelSettingsPage({ onClose, isAdmin }) {
  const [channels, setChannels] = useState([]);
  const [bindings, setBindings] = useState([]);
  const [models, setModels] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [bindModalVisible, setBindModalVisible] = useState(false);
  const [bindCodeModalVisible, setBindCodeModalVisible] = useState(false);
  const [bindCode, setBindCode] = useState('');
  const [bindCodeLoading, setBindCodeLoading] = useState(false);
  const [editingChannel, setEditingChannel] = useState(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [bindForm] = Form.useForm();
  const [testing, setTesting] = useState(null);

  const loadChannels = useCallback(async () => {
    setLoading(true);
    try {
      const res = await channelService.listChannels();
      if (res.success) setChannels(res.data || []);
    } catch (e) { /* ignore */ }
    try {
      const bRes = await channelService.listBindings();
      if (bRes.success) setBindings(bRes.data || []);
    } catch (e) { /* ignore */ }
    try {
      const mRes = await adminService.getAllModels();
      if (mRes.success) setModels(mRes.data || []);
    } catch (e) { /* ignore */ }
    if (isAdmin) {
      try {
        const uRes = await adminService.listUsers();
        if (uRes.success) setUsers(uRes.data || []);
      } catch (e) { /* ignore */ }
    }
    setLoading(false);
  }, [isAdmin]);

  useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const config = {};
      const fields = ['app_id', 'app_secret', 'verify_token', 'encrypt_key', 'bot_name'];
      fields.forEach(f => { if (values[f]) config[f] = values[f]; });

      if (values.model) {
        const [providerID, modelID] = values.model.split('|', 2);
        config.model = { providerID, modelID };
      }

      await channelService.createChannel({
        channel_type: values.channel_type,
        name: values.name,
        config,
      });
      message.success('渠道创建成功');
      setModalVisible(false);
      form.resetFields();
      loadChannels();
    } catch (e) {
      if (e.response?.data?.detail) {
        message.error(e.response.data.detail);
      }
    }
  };

  const handleDelete = async (id) => {
    try {
      await channelService.deleteChannel(id);
      message.success('渠道已删除');
      loadChannels();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleTest = async (id) => {
    setTesting(id);
    try {
      const res = await channelService.testChannel(id);
      if (res.success) {
        message.success(res.message || '连接测试成功');
      } else {
        message.error(res.message || '连接测试失败');
      }
    } catch (e) {
      message.error('测试失败');
    }
    setTesting(null);
  };

  const getCallbackUrl = (channel) => {
    if (!channel) return '';
    const base = window.location.origin;
    return `${base}/api/channels/${channel.id}/callback`;
  };

  const getModelDisplay = (channel) => {
    const cfg = channel.config || {};
    if (typeof cfg === 'string') { try { JSON.parse(cfg); } catch { return '-'; } }
    const m = cfg.model;
    if (!m || !m.modelID) return <Text type="secondary">全局默认</Text>;
    return <Tag color="blue">{m.modelID}</Tag>;
  };

  const openEditModal = (channel) => {
    setEditingChannel(channel);
    const cfg = typeof channel.config === 'string' ? JSON.parse(channel.config || '{}') : (channel.config || {});
    const m = cfg.model;
    editForm.setFieldsValue({
      model: m && m.providerID && m.modelID ? `${m.providerID}|${m.modelID}` : undefined,
    });
    setEditModalVisible(true);
  };

  const openBindModal = () => {
    bindForm.resetFields();
    setBindModalVisible(true);
  };

  const handleAdminBind = async () => {
    try {
      const values = await bindForm.validateFields();
      await channelService.adminCreateBinding(values.channel_id, values.external_user_id, values.user_id);
      message.success('绑定成功');
      setBindModalVisible(false);
      loadChannels();
    } catch (e) {
      message.error(e.response?.data?.detail || '绑定失败');
    }
  };

  const handleGenerateBindCode = async () => {
    setBindCodeLoading(true);
    try {
      const res = await channelService.generateBindCode();
      if (res.success) {
        setBindCode(res.data.code);
        setBindCodeModalVisible(true);
      }
    } catch (e) {
      message.error('生成绑定码失败');
    }
    setBindCodeLoading(false);
  };

  const handleEditModel = async () => {
    try {
      const values = await editForm.validateFields();
      const newConfig = typeof editingChannel.config === 'string'
        ? JSON.parse(editingChannel.config || '{}')
        : { ...(editingChannel.config || {}) };

      if (values.model) {
        const [providerID, modelID] = values.model.split('|', 2);
        newConfig.model = { providerID, modelID };
      } else {
        delete newConfig.model;
      }

      await channelService.updateChannel(editingChannel.id, { config: newConfig });
      message.success('模型配置已更新');
      setEditModalVisible(false);
      loadChannels();
    } catch (e) {
      message.error('更新失败');
    }
  };

  const columns = [
    {
      title: '名称', dataIndex: 'name', key: 'name',
      render: (text) => <Text strong>{text}</Text>,
    },
    {
      title: '类型', dataIndex: 'channel_type', key: 'type',
      render: (t) => <Tag color={t === 'feishu' ? 'blue' : t === 'wecom' ? 'green' : 'orange'}>
        {t === 'feishu' ? '飞书' : t === 'wecom' ? '企业微信' : '钉钉'}
      </Tag>,
    },
    {
      title: '模型', key: 'model', width: 160,
      render: (_, record) => getModelDisplay(record),
    },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s) => s === 'active'
        ? <Tag icon={<CheckCircleOutlined />} color="success">活跃</Tag>
        : <Tag icon={<CloseCircleOutlined />} color="default">未激活</Tag>,
    },
    {
      title: '回调 URL', key: 'callback',
      render: (_, record) => (
        <Text copyable code style={{ fontSize: 11 }}>{getCallbackUrl(record)}</Text>
      ),
    },
    {
      title: '操作', key: 'actions',
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<ApiOutlined />} onClick={() => openEditModal(record)}>
            模型
          </Button>
          <Button size="small" icon={<SendOutlined />} onClick={() => handleTest(record.id)} loading={testing === record.id}>
            测试
          </Button>
          {isAdmin && (
            <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
              <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <LinkOutlined /> 渠道管理
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadChannels}>刷新</Button>
          <Button icon={<LinkOutlined />} onClick={handleGenerateBindCode} loading={bindCodeLoading}>
            绑定飞书
          </Button>
          {isAdmin && (
            <>
              <Button icon={<PlusOutlined />} onClick={openBindModal}>
                手动绑定
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
                添加渠道
              </Button>
            </>
          )}
        </Space>
      </div>

      <Alert
        message="飞书接入指南"
        description={
          <ol style={{ margin: 0, paddingLeft: 20 }}>
            <li>前往飞书开放平台创建企业自建应用</li>
            <li>开启机器人能力，配置事件订阅 URL 为上方回调地址</li>
            <li>订阅 <code>im.message.receive_v1</code> 事件</li>
            <li>填写 App ID 和 App Secret</li>
            <li>点击"测试"验证连接</li>
          </ol>
        }
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Table
        dataSource={channels}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
      />

      {bindings.length > 0 && (
        <>
          <Divider>绑定记录</Divider>
          <Table
            dataSource={bindings}
            columns={[
              { title: '渠道 ID', dataIndex: 'channel_id', key: 'ch', width: 80 },
              {
                title: '飞书用户', dataIndex: 'external_user_id', key: 'ext',
                render: (t) => <Text code style={{ fontSize: 11 }}>{t}</Text>,
              },
              {
                title: '系统用户', key: 'user',
                render: (_, r) => r.username
                  ? <Tag color="blue">{r.username}</Tag>
                  : <Text type="secondary">渠道默认</Text>,
              },
              { title: '会话 ID', dataIndex: 'session_id', key: 'sess', ellipsis: true },
              { title: '最后活跃', dataIndex: 'last_active_at', key: 'time', width: 160 },
              {
                title: '操作', key: 'act', width: 120,
                render: (_, r) => (
                  <Space>
                    {isAdmin && (
                      <Button size="small" onClick={() => {
                        bindForm.setFieldsValue({
                          channel_id: r.channel_id,
                          external_user_id: r.external_user_id,
                          user_id: r.user_id,
                        });
                        setBindModalVisible(true);
                      }}>改绑</Button>
                    )}
                    <Popconfirm title="确认解绑？" onConfirm={async () => {
                      await channelService.deleteBinding(r.id);
                      loadChannels();
                    }}>
                      <Button size="small" danger>解绑</Button>
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
            rowKey="id"
            size="small"
            pagination={false}
          />
        </>
      )}

      <Modal
        title="添加渠道"
        open={modalVisible}
        onOk={handleCreate}
        onCancel={() => { setModalVisible(false); form.resetFields(); }}
        okText="创建"
        width={520}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="渠道名称" rules={[{ required: true }]}>
            <Input placeholder="例如：公司飞书机器人" />
          </Form.Item>
          <Form.Item name="channel_type" label="渠道类型" rules={[{ required: true }]}>
            <Select placeholder="选择渠道类型">
              <Option value="feishu">飞书</Option>
              <Option value="wecom" disabled>企业微信（开发中）</Option>
              <Option value="dingtalk" disabled>钉钉（开发中）</Option>
            </Select>
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.channel_type !== cur.channel_type}>
            {({ getFieldValue }) =>
              getFieldValue('channel_type') === 'feishu' ? <FeishuConfigForm form={form} models={models} /> : null
            }
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑模型 - ${editingChannel?.name || ''}`}
        open={editModalVisible}
        onOk={handleEditModel}
        onCancel={() => { setEditModalVisible(false); editForm.resetFields(); }}
        okText="保存"
        width={480}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="model" label="默认模型">
            <Select placeholder="留空则使用全局默认模型" allowClear showSearch optionFilterProp="label" loading={!models}>
              {(models || []).map(m => (
                <Option key={`${m.providerID}|${m.modelID}`} value={`${m.providerID}|${m.modelID}`} label={`${m.name || m.modelID}`}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{m.name || m.modelID}</span>
                    <Text type="secondary" style={{ fontSize: 11 }}>{m.providerName || m.providerID}</Text>
                  </div>
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="管理员手动绑定"
        open={bindModalVisible}
        onOk={handleAdminBind}
        onCancel={() => { setBindModalVisible(false); bindForm.resetFields(); }}
        okText="绑定"
        width={520}
      >
        <Form form={bindForm} layout="vertical">
          <Form.Item name="channel_id" label="渠道" rules={[{ required: true, message: '请选择渠道' }]}>
            <Select placeholder="选择渠道">
              {channels.map(c => (
                <Option key={c.id} value={c.id}>{c.name}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="external_user_id" label="飞书用户 Open ID" rules={[{ required: true, message: '请输入飞书用户 Open ID' }]}>
            <Input placeholder="ou_xxxxxxxxxxxxxxxx" />
          </Form.Item>
          <Form.Item name="user_id" label="系统用户" rules={[{ required: true, message: '请选择系统用户' }]}>
            <Select placeholder="选择系统用户" showSearch optionFilterProp="label">
              {users.map(u => (
                <Option key={u.id} value={u.id} label={u.username}>
                  {u.username} {u.is_admin ? '(管理员)' : ''}
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="绑定飞书账号"
        open={bindCodeModalVisible}
        onCancel={() => setBindCodeModalVisible(false)}
        footer={<Button onClick={() => setBindCodeModalVisible(false)}>关闭</Button>}
        width={420}
      >
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <Text type="secondary" style={{ fontSize: 13 }}>
            请在飞书中向机器人发送以下绑定码（5 分钟内有效）：
          </Text>
          <div style={{
            fontSize: 36, fontWeight: 'bold', letterSpacing: 8,
            margin: '20px 0', padding: '16px', background: '#f5f5f5',
            borderRadius: 8, fontFamily: 'monospace',
          }}>
            {bindCode}
          </div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            绑定后，您在飞书中的对话将使用您的工作空间
          </Text>
        </div>
      </Modal>
    </div>
  );
}
