import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Switch, Space,
  message, Popconfirm, Tag, Typography, Breadcrumb, Spin, Collapse,
  Menu, Layout, Select, Drawer,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  UserOutlined, HomeOutlined, ArrowLeftOutlined,
  ApiOutlined, DownOutlined, UpOutlined,
  SettingOutlined, CloudOutlined, CloudServerOutlined, KeyOutlined,
  BarChartOutlined, SafetyOutlined, ThunderboltOutlined,
  MenuOutlined,
} from '@ant-design/icons';
import {
  Link, useNavigate, useLocation,
} from 'react-router-dom';
import { adminService } from '../services/api';
import UsageStats from '../components/UsageStats';
import ToolPermissionManager from '../components/ToolPermissionManager';
import SkillManager from '../components/SkillManager';

const { Title, Text } = Typography;
const { Sider, Content } = Layout;

function ModelPermissionModal({ visible, userId, username, onClose }) {
  const [allModels, setAllModels] = useState([]);
  const [permissions, setPermissions] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeKeys, setActiveKeys] = useState([]);
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    setActiveKeys([]);
    setSearchText('');
    Promise.all([
      adminService.getAllModels(),
      adminService.getUserModels(userId),
    ])
      .then(([modelsRes, permsRes]) => {
        const models = modelsRes.data || [];
        setAllModels(models);
        const perms = {};
        if (permsRes.data?.permissions) {
          for (const p of permsRes.data.permissions) {
            const key = `${p.modelID}|${p.providerID}`;
            perms[key] = {
              enabled: p.enabled,
              monthlyLimit: p.monthlyLimit,
              currentUsage: p.currentUsage || 0,
            };
          }
        }
        setPermissions(perms);
      })
      .catch(() => message.error('加载模型数据失败'))
      .finally(() => setLoading(false));
  }, [visible, userId]);

  const permKey = (modelID, providerID) => `${modelID}|${providerID}`;

  const handleToggle = (modelID, providerID, enabled) => {
    const key = permKey(modelID, providerID);
    setPermissions(prev => ({
      ...prev,
      [key]: { ...prev[key], enabled, monthlyLimit: prev[key]?.monthlyLimit || 0, currentUsage: prev[key]?.currentUsage || 0 },
    }));
  };

  const handleLimitChange = (modelID, providerID, monthlyLimit) => {
    const key = permKey(modelID, providerID);
    setPermissions(prev => ({
      ...prev,
      [key]: { ...prev[key], monthlyLimit: monthlyLimit || 0 },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const models = [];
      for (const m of allModels) {
        const key = permKey(m.modelID, m.providerID);
        const p = permissions[key];
        if (p?.enabled) {
          models.push({
            modelID: m.modelID,
            providerID: m.providerID,
            enabled: true,
            monthlyLimit: p.monthlyLimit || 0,
          });
        }
      }
      const result = await adminService.setUserModels(userId, models);
      if (result.success) {
        message.success('模型权限已保存');
        onClose(true);
      }
    } catch (err) {
      message.error(err.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const filteredModels = searchText
    ? allModels.filter(m => (m.name || m.modelID).toLowerCase().includes(searchText.toLowerCase()))
    : allModels;

  const grouped = {};
  for (const m of filteredModels) {
    const key = m.providerID;
    if (!grouped[key]) {
      grouped[key] = { name: m.providerName || m.providerID, models: [] };
    }
    grouped[key].models.push(m);
  }

  const collapseItems = Object.entries(grouped).map(([providerID, group]) => {
    const enabledCount = group.models.filter(m => permissions[permKey(m.modelID, providerID)]?.enabled).length;
    return {
      key: providerID,
      label: (
        <Space>
          <span>{group.name}</span>
          <Tag color={enabledCount > 0 ? 'blue' : 'default'} style={{ margin: 0 }}>
            {enabledCount}/{group.models.length} 已启用
          </Tag>
        </Space>
      ),
      children: group.models.map(m => {
        const p = permissions[permKey(m.modelID, providerID)] || {};
        return (
          <div key={m.modelID} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '6px 0', borderBottom: '1px solid #fafafa',
          }}>
            <span style={{ flex: 1, fontSize: 13 }}>{m.name || m.modelID}</span>
            <Space size="middle">
              {p.enabled && p.currentUsage > 0 && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  已用 {p.currentUsage} 次{p.monthlyLimit > 0 ? ` / ${p.monthlyLimit}` : ''}
                </Text>
              )}
              <Switch
                size="small"
                checked={p.enabled || false}
                onChange={(v) => handleToggle(m.modelID, providerID, v)}
              />
              {p.enabled && (
                <Space size={4}>
                  <Text style={{ fontSize: 12, whiteSpace: 'nowrap' }}>月限:</Text>
                  <InputNumber
                    size="small"
                    min={0}
                    value={p.monthlyLimit || 0}
                    onChange={(v) => handleLimitChange(m.modelID, providerID, v)}
                    style={{ width: 80 }}
                    placeholder="0"
                  />
                  <Text type="secondary" style={{ fontSize: 11 }}>0=不限</Text>
                </Space>
              )}
            </Space>
          </div>
        );
      }),
    };
  });

  const expandAll = () => setActiveKeys(Object.keys(grouped));
  const collapseAll = () => setActiveKeys([]);

  return (
    <Modal
      title={`${username} 的模型权限`}
      open={visible}
      onCancel={() => onClose(false)}
      width={700}
      footer={[
        <Button key="cancel" onClick={() => onClose(false)}>取消</Button>,
        <Button key="save" type="primary" loading={saving} onClick={handleSave}>保存</Button>,
      ]}
      bodyStyle={{ maxHeight: 520, overflowY: 'auto' }}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}><Spin /></div>
      ) : allModels.length === 0 ? (
        <Text type="secondary">暂无可用模型</Text>
      ) : (
        <div style={{ marginBottom: 8 }}>
          <Space style={{ marginBottom: 8, width: '100%', justifyContent: 'space-between' }}>
            <Input
              placeholder="搜索模型名称..."
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              allowClear
              style={{ width: 220 }}
              size="small"
            />
            <Space>
              <Button size="small" icon={<UpOutlined />} onClick={expandAll}>全部展开</Button>
              <Button size="small" icon={<DownOutlined />} onClick={collapseAll}>全部折叠</Button>
            </Space>
          </Space>
          {Object.keys(grouped).length === 0 ? (
            <Text type="secondary">未找到匹配 "{searchText}" 的模型</Text>
          ) : (
            <Collapse
              activeKey={activeKeys}
              onChange={setActiveKeys}
              items={collapseItems}
              ghost
            />
          )}
        </div>
      )}
      </Modal>
  );
}

function ToolPermissionModal({ visible, userId, username, onClose }) {
  const [tools, setTools] = useState([]);
  const [permissions, setPermissions] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    setSearchText('');
    adminService.getUserTools(userId)
      .then((res) => {
        if (res.success) {
          setTools(res.data || []);
          const perms = {};
          for (const t of res.data || []) {
            perms[t.tool_name] = {
              global_action: t.global_action || 'allow',
              user_action: t.user_action || 'allow',
              has_override: t.has_override || 0,
            };
          }
          setPermissions(perms);
        }
      })
      .catch(() => message.error('加载工具权限失败'))
      .finally(() => setLoading(false));
  }, [visible, userId]);

  const handleActionChange = async (toolName, action) => {
    try {
      await adminService.setUserTool(userId, toolName, action);
      setPermissions(prev => ({
        ...prev,
        [toolName]: { ...prev[toolName], user_action: action, has_override: 1 },
      }));
      message.success(`${toolName} 已设置为 ${action === 'deny' ? '拒绝' : action === 'ask' ? '审批' : '允许'}`);
    } catch {
      message.error('更新失败');
    }
  };

  const handleRemoveOverride = async (toolName) => {
    try {
      await adminService.removeUserTool(userId, toolName);
      setPermissions(prev => ({
        ...prev,
        [toolName]: { ...prev[toolName], user_action: prev[toolName].global_action, has_override: 0 },
      }));
      message.success(`${toolName} 已恢复全局设置`);
    } catch {
      message.error('移除失败');
    }
  };

  const filteredTools = searchText
    ? tools.filter(t => t.tool_name.toLowerCase().includes(searchText.toLowerCase()))
    : tools;

  const grouped = { dangerous: [], moderate: [], safe: [] };
  for (const t of filteredTools) {
    const level = t.risk_level || 'safe';
    if (!grouped[level]) grouped[level] = [];
    grouped[level].push(t);
  }

  const ACTION_CONFIG = {
    deny: { color: '#ff4d4f', label: '拒绝' },
    ask: { color: '#faad14', label: '审批' },
    allow: { color: '#52c41a', label: '允许' },
  };

  const renderToolRow = (t) => {
    const p = permissions[t.tool_name] || { global_action: 'allow', user_action: 'allow', has_override: 0 };
    return (
      <div key={t.tool_name} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 0', borderBottom: '1px solid #fafafa',
      }}>
        <div style={{ flex: 1 }}>
          <Tag color="blue">{t.tool_name}</Tag>
          {p.has_override ? (
            <Text type="secondary" style={{ fontSize: 11 }}>
              全局: <Tag size="small" color={ACTION_CONFIG[p.global_action]?.color}>{ACTION_CONFIG[p.global_action]?.label}</Tag>
            </Text>
          ) : null}
        </div>
        <Space size="middle">
          <Select
            value={p.has_override ? p.user_action : p.global_action}
            onChange={(val) => handleActionChange(t.tool_name, val)}
            size="small"
            style={{ width: 90 }}
          >
            <Select.Option value="deny"><Text style={{ color: '#ff4d4f' }}>拒绝</Text></Select.Option>
            <Select.Option value="ask"><Text style={{ color: '#faad14' }}>审批</Text></Select.Option>
            <Select.Option value="allow"><Text style={{ color: '#52c41a' }}>允许</Text></Select.Option>
          </Select>
          {p.has_override && (
            <Button size="small" type="text" onClick={() => handleRemoveOverride(t.tool_name)} title="恢复全局设置">
              重置
            </Button>
          )}
        </Space>
      </div>
    );
  };

  return (
    <Modal
      title={`${username} 的工具权限`}
      open={visible}
      onCancel={() => onClose(false)}
      width={600}
      footer={[
        <Button key="close" onClick={() => onClose(false)}>关闭</Button>,
      ]}
      bodyStyle={{ maxHeight: 520, overflowY: 'auto' }}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}><Spin /></div>
      ) : tools.length === 0 ? (
        <Text type="secondary">暂无可用工具</Text>
      ) : (
        <div>
          <Input
            placeholder="搜索工具名称..."
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            allowClear
            style={{ width: 200, marginBottom: 12 }}
            size="small"
          />
          {grouped.dangerous.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Text type="dangerous" style={{ fontSize: 12, color: '#ff4d4f' }}>危险工具</Text>
              {grouped.dangerous.map(renderToolRow)}
            </div>
          )}
          {grouped.moderate.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12, color: '#faad14' }}>敏感工具</Text>
              {grouped.moderate.map(renderToolRow)}
            </div>
          )}
          {grouped.safe.length > 0 && (
            <div>
              <Text type="secondary" style={{ fontSize: 12, color: '#52c41a' }}>安全工具</Text>
              {grouped.safe.map(renderToolRow)}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function SkillPermissionModal({ visible, userId, username, onClose }) {
  const [skills, setSkills] = useState([]);
  const [permissions, setPermissions] = useState({});
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    setSearchText('');
    adminService.getUserSkills(userId)
      .then((res) => {
        if (res.success) {
          setSkills(res.data || []);
          const perms = {};
          for (const s of res.data || []) {
            perms[s.skill_name] = {
              globally_enabled: s.globally_enabled || 0,
              user_action: s.user_action || 'allow',
              has_override: s.has_override || 0,
            };
          }
          setPermissions(perms);
        }
      })
      .catch(() => message.error('加载技能权限失败'))
      .finally(() => setLoading(false));
  }, [visible, userId]);

  const handleActionChange = async (skillName, action) => {
    try {
      await adminService.setUserSkill(userId, skillName, action);
      setPermissions(prev => ({
        ...prev,
        [skillName]: { ...prev[skillName], user_action: action, has_override: 1 },
      }));
      message.success(`${skillName} 已设置为 ${action === 'deny' ? '禁用' : '启用'}`);
    } catch {
      message.error('更新失败');
    }
  };

  const handleRemoveOverride = async (skillName) => {
    try {
      await adminService.removeUserSkill(userId, skillName);
      setPermissions(prev => ({
        ...prev,
        [skillName]: { ...prev[skillName], user_action: prev[skillName].globally_enabled ? 'allow' : 'deny', has_override: 0 },
      }));
      message.success(`${skillName} 已恢复全局设置`);
    } catch {
      message.error('移除失败');
    }
  };

  const filteredSkills = searchText
    ? skills.filter(s => s.skill_name.toLowerCase().includes(searchText.toLowerCase()))
    : skills;

  const renderSkillRow = (s) => {
    const p = permissions[s.skill_name] || { globally_enabled: 1, user_action: 'allow', has_override: 0 };
    return (
      <div key={s.skill_name} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 0', borderBottom: '1px solid #fafafa',
      }}>
        <div style={{ flex: 1 }}>
          <Tag color="blue">{s.skill_name}</Tag>
          {p.has_override ? (
            <Text type="secondary" style={{ fontSize: 11 }}>
              全局: <Tag size="small" color={p.globally_enabled ? 'green' : 'red'}>{p.globally_enabled ? '启用' : '禁用'}</Tag>
            </Text>
          ) : null}
        </div>
        <Space size="middle">
          <Select
            value={p.has_override ? p.user_action : (p.globally_enabled ? 'allow' : 'deny')}
            onChange={(val) => handleActionChange(s.skill_name, val)}
            size="small"
            style={{ width: 90 }}
          >
            <Select.Option value="allow"><Text style={{ color: '#52c41a' }}>启用</Text></Select.Option>
            <Select.Option value="deny"><Text style={{ color: '#ff4d4f' }}>禁用</Text></Select.Option>
          </Select>
          {p.has_override && (
            <Button size="small" type="text" onClick={() => handleRemoveOverride(s.skill_name)} title="恢复全局设置">
              重置
            </Button>
          )}
        </Space>
      </div>
    );
  };

  return (
    <Modal
      title={`${username} 的技能权限`}
      open={visible}
      onCancel={() => onClose(false)}
      width={550}
      footer={[
        <Button key="close" onClick={() => onClose(false)}>关闭</Button>,
      ]}
      bodyStyle={{ maxHeight: 480, overflowY: 'auto' }}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}><Spin /></div>
      ) : skills.length === 0 ? (
        <Text type="secondary">暂无可用技能，请先同步技能列表</Text>
      ) : (
        <div>
          <Input
            placeholder="搜索技能名称..."
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            allowClear
            style={{ width: 200, marginBottom: 12 }}
            size="small"
          />
          {filteredSkills.map(renderSkillRow)}
        </div>
      )}
    </Modal>
  );
}

function UserManagement() {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [permModal, setPermModal] = useState({ visible: false, userId: null, username: '' });
  const [toolPermModal, setToolPermModal] = useState({ visible: false, userId: null, username: '' });
  const [skillPermModal, setSkillPermModal] = useState({ visible: false, userId: null, username: '' });
  const [form] = Form.useForm();

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminService.listUsers();
      if (result.success) {
        setUsers(result.data || []);
      }
    } catch (err) {
      message.error('获取用户列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleCreate = () => {
    setEditingUser(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditingUser(record);
    form.setFieldsValue({
      username: record.username,
      is_admin: Boolean(record.is_admin),
      disabled: Boolean(record.disabled),
      password: undefined,
    });
    setModalVisible(true);
  };

  const handleDelete = async (userId) => {
    try {
      const result = await adminService.deleteUser(userId);
      if (result.success) {
        message.success('删除成功');
        fetchUsers();
      }
    } catch (err) {
      message.error(err.response?.data?.detail || '删除失败');
    }
  };

  const handleInitWorkspace = async (record) => {
    try {
      const result = await adminService.initUserWorkspace(record.id);
      if (result.success) {
        message.success('工作空间已初始化');
        fetchUsers();
      } else {
        message.error(result.error || '初始化失败');
      }
    } catch (err) {
      message.error(err.response?.data?.detail || '初始化失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingUser) {
        const updateData = {
          is_admin: values.is_admin || false,
          disabled: values.disabled || false,
        };
        if (values.password) {
          updateData.password = values.password;
        }
        const result = await adminService.updateUser(editingUser.id, updateData);
        if (result.success) {
          message.success('更新成功');
          setModalVisible(false);
          fetchUsers();
        }
      } else {
        const result = await adminService.createUser({
          username: values.username,
          password: values.password,
          is_admin: values.is_admin || false,
          disabled: values.disabled || false,
        });
        if (result.success) {
          message.success('创建成功');
          setModalVisible(false);
          fetchUsers();
        }
      }
    } catch (err) {
      if (err.response?.data?.detail) {
        message.error(err.response.data.detail);
      } else if (!err.errorFields) {
        message.error(editingUser ? '更新失败' : '创建失败');
      }
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 50,
    },
    {
      title: '用户名',
      dataIndex: 'username',
      width: 120,
      render: (text) => (
        <span><UserOutlined style={{ marginRight: 6 }} />{text}</span>
      ),
    },
    {
      title: '角色',
      dataIndex: 'is_admin',
      width: 90,
      render: (val) => val ? <Tag color="blue">管理员</Tag> : <Tag>普通</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'disabled',
      width: 70,
      render: (val) => val ? <Tag color="red">禁用</Tag> : <Tag color="green">启用</Tag>,
    },
    {
      title: '工作空间',
      dataIndex: 'workspace_path',
      width: 160,
      ellipsis: true,
      responsive: ['lg'],
      render: (val) => val ? (
        <Text type="secondary" style={{ fontSize: 12 }} title={val}>
          {val.split('/').slice(-2).join('/')}
        </Text>
      ) : <Tag color="orange">未初始化</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 160,
      responsive: ['xl'],
      render: (val) => val ? new Date(val).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      width: 140,
      render: (_, record) => (
        <Space size={4}>
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            title="编辑"
          />
          <Button
            type="text"
            size="small"
            icon={<ApiOutlined />}
            onClick={() => setPermModal({ visible: true, userId: record.id, username: record.username })}
            title="模型权限"
          />
          <Button
            type="text"
            size="small"
            icon={<SafetyOutlined />}
            onClick={() => setToolPermModal({ visible: true, userId: record.id, username: record.username })}
            title="工具权限"
          />
          <Button
            type="text"
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => setSkillPermModal({ visible: true, userId: record.id, username: record.username })}
            title="技能权限"
          />
          {!record.workspace_path && (
            <Button
              type="text"
              size="small"
              onClick={() => handleInitWorkspace(record)}
              title="初始化工作空间"
              style={{ color: '#fa8c16', fontSize: 12 }}
            >
              初始化
            </Button>
          )}
          <Popconfirm
            title="确定删除此用户？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} title="删除" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>用户管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          新增用户
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="middle"
        scroll={{ x: 'max-content' }}
      />

      <Modal
        title={editingUser ? '编辑用户' : '新增用户'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        okText="确定"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={editingUser ? [] : [
              { required: true, message: '请输入用户名' },
              { min: 2, message: '用户名至少 2 个字符' },
            ]}
          >
            <Input
              placeholder={editingUser ? editingUser.username : '请输入用户名'}
              disabled={!!editingUser}
              prefix={<UserOutlined />}
            />
          </Form.Item>

          <Form.Item
            name="password"
            label={editingUser ? '新密码（留空不修改）' : '密码'}
            rules={editingUser ? [] : [
              { required: true, message: '请输入密码' },
              { min: 4, message: '密码至少 4 个字符' },
            ]}
          >
            <Input.Password placeholder={editingUser ? '留空则不修改密码' : '请输入密码'} />
          </Form.Item>

          <Form.Item name="is_admin" valuePropName="checked" initialValue={false}>
            <Switch checkedChildren="管理员" unCheckedChildren="普通用户" />
          </Form.Item>

          <Form.Item name="disabled" valuePropName="checked" initialValue={false}>
            <Switch checkedChildren="禁用" unCheckedChildren="启用" />
          </Form.Item>
        </Form>
      </Modal>

      <ModelPermissionModal
        visible={permModal.visible}
        userId={permModal.userId}
        username={permModal.username}
        onClose={(refresh) => {
          setPermModal({ visible: false, userId: null, username: '' });
          if (refresh) fetchUsers();
        }}
      />

      <ToolPermissionModal
        visible={toolPermModal.visible}
        userId={toolPermModal.userId}
        username={toolPermModal.username}
        onClose={() => {
          setToolPermModal({ visible: false, userId: null, username: '' });
        }}
      />

      <SkillPermissionModal
        visible={skillPermModal.visible}
        userId={skillPermModal.userId}
        username={skillPermModal.username}
        onClose={() => {
          setSkillPermModal({ visible: false, userId: null, username: '' });
        }}
      />
    </div>
  );
}

function ModelConfiguration() {
  const [providers, setProviders] = useState([]);
  const [providerAuth, setProviderAuth] = useState({});
  const [loading, setLoading] = useState(false);
  const [savingKey, setSavingKey] = useState(null);
  const [savingDefaultKey, setSavingDefaultKey] = useState(null);
  const [apiKeys, setApiKeys] = useState({});
  const [defaultModelBuild, setDefaultModelBuild] = useState(null);
  const [defaultModelPlan, setDefaultModelPlan] = useState(null);
  const [providerSearchText, setProviderSearchText] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [providersRes, authRes, sysConfigRes] = await Promise.all([
        adminService.getOpencodeProviders(),
        adminService.getOpencodeProviderAuth(),
        adminService.getSystemConfig(),
      ]);

      if (providersRes.success) {
        const data = providersRes.data;
        const all = data.all || [];
        const connected = data.connected || [];
        setProviders(all.map(p => ({
          ...p,
          isConnected: connected.includes(p.id),
        })));
      }

      if (authRes.success) {
        setProviderAuth(authRes.data || {});
      }

      if (sysConfigRes.success) {
        const sc = sysConfigRes.data || {};
        setDefaultModelBuild(sc.default_build_model || null);
        setDefaultModelPlan(sc.default_plan_model || null);
      }
    } catch (err) {
      message.error('加载服务商数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSaveApiKey = async (providerId) => {
    const apiKey = apiKeys[providerId] || '';
    setSavingKey(providerId);
    try {
      const result = await adminService.setOpencodeProviderAuth(providerId, { api_key: apiKey });
      if (result.success) {
        message.success('API Key 已保存，opencode 将自动尝试连接');
        loadData();
      } else {
        message.error(result.error || '保存失败');
      }
    } catch (err) {
      message.error('保存失败');
    } finally {
      setSavingKey(null);
    }
  };

  const handleSetDefaultModel = async (providerID, modelID, agent) => {
    const key = `${providerID}|${modelID}|${agent}`;
    setSavingDefaultKey(key);
    try {
      const configKey = agent === 'build' ? 'default_build_model' : 'default_plan_model';
      const configValue = `${providerID}|${modelID}`;
      if (agent === 'build') {
        setDefaultModelBuild({ providerID, modelID });
      } else {
        setDefaultModelPlan({ providerID, modelID });
      }
      const result = await adminService.setSystemConfig(configKey, configValue);
      if (result.success) {
        message.success(`${agent === 'build' ? 'Build' : 'Plan'} 默认模型已更新`);
      } else {
        message.error(result.error || '设置失败');
        loadData();
      }
    } catch (err) {
      message.error('设置失败');
      loadData();
    } finally {
      setSavingDefaultKey(null);
    }
  };

  const handleClearDefaultModel = async (agent) => {
    setSavingDefaultKey(agent);
    try {
      const configKey = agent === 'build' ? 'default_build_model' : 'default_plan_model';
      const result = await adminService.setSystemConfig(configKey, '');
      if (result.success) {
        if (agent === 'build') setDefaultModelBuild(null);
        else setDefaultModelPlan(null);
        message.success(`${agent === 'build' ? 'Build' : 'Plan'} 默认模型已清除`);
      } else {
        message.error(result.error || '清除失败');
      }
    } catch (err) {
      message.error('清除失败');
    } finally {
      setSavingDefaultKey(null);
    }
  };

  const isDefaultBuild = (providerID, modelID) =>
    defaultModelBuild?.providerID === providerID && defaultModelBuild?.modelID === modelID;

  const isDefaultPlan = (providerID, modelID) =>
    defaultModelPlan?.providerID === providerID && defaultModelPlan?.modelID === modelID;

  const filteredProviders = providerSearchText
    ? providers.filter(p => (p.name || p.id).toLowerCase().includes(providerSearchText.toLowerCase()))
    : providers;

  const buildModelOptions = [];
  for (const p of filteredProviders) {
    if (!p.isConnected) continue;
    const models = p.models || {};
    for (const [modelId, info] of Object.entries(models)) {
      buildModelOptions.push({
        value: `${p.id}|${modelId}`,
        label: `${p.name || p.id} / ${info.name || modelId}`,
        providerID: p.id,
        modelID: modelId,
      });
    }
  }

  const planModelOptions = buildModelOptions;

  const collapseItems = filteredProviders.map(p => {
    const models = p.models || {};
    const modelList = Object.entries(models).map(([modelId, info]) => ({
      id: modelId,
      name: info.name || info.model || modelId,
    }));
    return {
      key: p.id,
      label: (
        <Space>
          <CloudOutlined style={{ color: p.isConnected ? '#52c41a' : '#d9d9d9' }} />
          <span>{p.name || p.id}</span>
          <Tag color={p.isConnected ? 'green' : 'default'} style={{ margin: 0 }}>
            {p.isConnected ? '已连接' : '未连接'}
          </Tag>
          <Tag style={{ margin: 0 }}>{modelList.length} 个模型</Tag>
        </Space>
      ),
      children: (
        <div style={{ padding: '8px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <Space align="start">
              <KeyOutlined style={{ marginTop: 6, color: '#1890ff' }} />
              <div style={{ flex: 1 }}>
                <Text strong style={{ fontSize: 13 }}>API Key / 认证</Text>
                <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center' }}>
                  <Input.Password
                    placeholder="输入 API Key 后按保存"
                    value={apiKeys[p.id] || ''}
                    onChange={e => setApiKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
                    style={{ width: 360 }}
                    size="small"
                  />
                  <Button
                    type="primary"
                    size="small"
                    loading={savingKey === p.id}
                    onClick={() => handleSaveApiKey(p.id)}
                  >
                    保存
                  </Button>
                </div>
                {providerAuth[p.id] && (
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                    认证方式：{providerAuth[p.id].map(a => a.type || a.method || 'API Key').join(', ')}
                  </Text>
                )}
              </div>
            </Space>
          </div>
          {modelList.length > 0 && (
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>可用模型（点击⭐设为默认）：</Text>
              <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {modelList.map(m => {
                  const isBuild = isDefaultBuild(p.id, m.id);
                  const isPlan = isDefaultPlan(p.id, m.id);
                  return (
                    <div key={m.id} style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      background: isBuild || isPlan ? '#e6f7ff' : undefined,
                      border: isBuild || isPlan ? '1px solid #91d5ff' : '1px solid transparent',
                      borderRadius: 6,
                      padding: '2px 6px',
                    }}>
                      <Tag
                        style={{
                          fontSize: 12,
                          margin: 0,
                          background: isBuild ? '#1890ff' : isPlan ? '#722ed1' : undefined,
                          borderColor: isBuild ? '#1890ff' : isPlan ? '#722ed1' : undefined,
                          color: (isBuild || isPlan) ? '#fff' : undefined,
                        }}
                      >
                        {m.name}
                      </Tag>
                      <Space size={0}>
                        <Button
                          type="text"
                          size="small"
                          loading={savingDefaultKey === `${p.id}|${m.id}|build`}
                          onClick={() => isBuild ? handleClearDefaultModel('build') : handleSetDefaultModel(p.id, m.id, 'build')}
                          title="设为 Build 默认"
                          style={{
                            color: isBuild ? '#1890ff' : '#bfbfbf',
                            padding: '0 2px',
                            height: 20,
                            minWidth: 20,
                          }}
                        >
                          🔨{isBuild ? '★' : ''}
                        </Button>
                        <Button
                          type="text"
                          size="small"
                          loading={savingDefaultKey === `${p.id}|${m.id}|plan`}
                          onClick={() => isPlan ? handleClearDefaultModel('plan') : handleSetDefaultModel(p.id, m.id, 'plan')}
                          title="设为 Plan 默认"
                          style={{
                            color: isPlan ? '#722ed1' : '#bfbfbf',
                            padding: '0 2px',
                            height: 20,
                            minWidth: 20,
                          }}
                        >
                          📋{isPlan ? '★' : ''}
                        </Button>
                      </Space>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      ),
    };
  });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>模型配置</Title>
        <Button size="small" onClick={loadData} loading={loading}>刷新</Button>
      </div>

      {loading && providers.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 0' }}><Spin size="large" /></div>
      ) : (
        <>
          <Card
            size="small"
            title="服务商管理"
            extra={<Tag>{providers.length} 个服务商</Tag>}
            style={{ marginBottom: 16 }}
            bodyStyle={{ maxHeight: 480, overflowY: 'auto' }}
          >
            {providers.length === 0 ? (
              <Text type="secondary">暂无可用服务商，请确保 opencode server 已启动并连接了服务商</Text>
            ) : (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Input
                    placeholder="搜索服务商名称..."
                    value={providerSearchText}
                    onChange={e => setProviderSearchText(e.target.value)}
                    allowClear
                    style={{ width: 240 }}
                    size="small"
                    prefix={<span style={{ color: '#999' }}>🔍</span>}
                  />
                  {providerSearchText && (
                    <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                      找到 {filteredProviders.length} 个服务商
                    </Text>
                  )}
                </div>
                <Collapse items={collapseItems} ghost />
              </>
            )}
          </Card>

          {(defaultModelBuild || defaultModelPlan) && (
            <Card size="small" style={{ background: '#fafafa' }}>
              <Space size="large" wrap>
                {defaultModelBuild && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    🔨 Build 默认：<Text strong>{defaultModelBuild.modelID}</Text>
                    <Text type="secondary">（{defaultModelBuild.providerID}）</Text>
                  </Text>
                )}
                {defaultModelPlan && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    📋 Plan 默认：<Text strong>{defaultModelPlan.modelID}</Text>
                    <Text type="secondary">（{defaultModelPlan.providerID}）</Text>
                  </Text>
                )}
              </Space>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function OpenCodeService() {
  const [opencodeStatus, setOpencodeStatus] = useState({ running: false, version: '', autoStart: true, workdir: '', username: 'opencode', password: '' });
  const [opencodeConfig, setOpencodeConfig] = useState({ workdir: '', username: 'opencode', password: '', autoStart: true });
  const [savingKey, setSavingKey] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminService.getOpencodeStatus();
      if (res.success) {
        const os = res.data || {};
        setOpencodeStatus(os);
        setOpencodeConfig({
          workdir: os.workdir || '',
          username: os.username || 'opencode',
          password: os.password || '',
          autoStart: os.autoStart !== false,
        });
      }
    } catch (err) {
      message.error('加载状态失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSave = async () => {
    setSavingKey('opencode-config');
    try {
      await Promise.all([
        adminService.setSystemConfig('opencode_workdir', opencodeConfig.workdir),
        adminService.setSystemConfig('opencode_username', opencodeConfig.username),
        adminService.setSystemConfig('opencode_password', opencodeConfig.password),
        adminService.setSystemConfig('opencode_auto_start', opencodeConfig.autoStart ? 'true' : 'false'),
      ]);
      message.success('配置已保存');
      loadData();
    } catch (err) {
      message.error('保存失败');
    } finally {
      setSavingKey(null);
    }
  };

  const handleRestart = async () => {
    setSavingKey('opencode-restart');
    try {
      const result = await adminService.restartOpencode();
      if (result.success) {
        message.success('opencode 正在重启...');
        setTimeout(loadData, 3000);
      } else {
        message.error(result.error || '重启失败');
      }
    } catch (err) {
      message.error('重启失败');
    } finally {
      setSavingKey(null);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>opencode 服务</Title>
        <Button size="small" onClick={loadData} loading={loading}>刷新</Button>
      </div>

      <Card size="small" title="服务状态" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text type="secondary" style={{ fontSize: 12, width: 70 }}>服务状态</Text>
            <Tag color={opencodeStatus.running ? 'green' : 'red'}>
              {opencodeStatus.running ? `运行中${opencodeStatus.version ? ' v' + opencodeStatus.version : ''}` : '未运行'}
            </Tag>
            <Button size="small" loading={savingKey === 'opencode-restart'} onClick={handleRestart} danger>
              重启
            </Button>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <Text type="secondary" style={{ fontSize: 12, width: 70, paddingTop: 4 }}>工作目录</Text>
            <Input
              placeholder="/path/to/DATAAGENT"
              value={opencodeConfig.workdir}
              onChange={e => setOpencodeConfig(prev => ({ ...prev, workdir: e.target.value }))}
              style={{ flex: 1 }}
              size="small"
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <Text type="secondary" style={{ fontSize: 12, width: 70, paddingTop: 4 }}>用户名</Text>
            <Input
              placeholder="opencode"
              value={opencodeConfig.username}
              onChange={e => setOpencodeConfig(prev => ({ ...prev, username: e.target.value }))}
              style={{ width: 160 }}
              size="small"
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <Text type="secondary" style={{ fontSize: 12, width: 70, paddingTop: 4 }}>密码</Text>
            <Input.Password
              placeholder="opencode 服务密码"
              value={opencodeConfig.password}
              onChange={e => setOpencodeConfig(prev => ({ ...prev, password: e.target.value }))}
              style={{ width: 240 }}
              size="small"
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text type="secondary" style={{ fontSize: 12, width: 70 }}>自动启动</Text>
            <Switch
              size="small"
              checked={opencodeConfig.autoStart}
              onChange={v => setOpencodeConfig(prev => ({ ...prev, autoStart: v }))}
              checkedChildren="开"
              unCheckedChildren="关"
            />
            <Text type="secondary" style={{ fontSize: 11 }}>后端启动时自动拉起 opencode</Text>
          </div>
          <div>
            <Button type="primary" size="small" loading={savingKey === 'opencode-config'} onClick={handleSave}>
              保存配置
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

const AdminPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [selectedKey, setSelectedKey] = useState('users');

  const selectedKeyFromPath = location.pathname.includes('model-config') ? 'model-config' : location.pathname.includes('opencode') ? 'opencode' : 'users';
  useEffect(() => {
    setSelectedKey(selectedKeyFromPath);
  }, [selectedKeyFromPath]);

  const menuItems = [
    {
      key: 'users',
      icon: <UserOutlined />,
      label: '用户管理',
    },
    {
      key: 'model-config',
      icon: <SettingOutlined />,
      label: '模型配置',
    },
    {
      key: 'opencode',
      icon: <CloudServerOutlined />,
      label: 'opencode 服务',
    },
    {
      key: 'usage-stats',
      icon: <BarChartOutlined />,
      label: '用量统计',
    },
    {
      key: 'tools',
      icon: <SafetyOutlined />,
      label: '工具权限',
    },
    {
      key: 'skills',
      icon: <ThunderboltOutlined />,
      label: '技能管理',
    },
  ];

  const renderContent = () => {
    if (selectedKey === 'users') {
      return <UserManagement />;
    }
    if (selectedKey === 'model-config') {
      return <ModelConfiguration />;
    }
    if (selectedKey === 'opencode') {
      return <OpenCodeService />;
    }
    if (selectedKey === 'usage-stats') {
      return <UsageStats visible={true} />;
    }
    if (selectedKey === 'tools') {
      return <ToolPermissionManager visible={true} />;
    }
    if (selectedKey === 'skills') {
      return <SkillManager visible={true} />;
    }
    return null;
  };

  // 移动端检测
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [drawerVisible, setDrawerVisible] = useState(false);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f7fa' }}>
      {/* 移动端汉堡菜单按钮 */}
      {isMobile && (
        <Button
          icon={<MenuOutlined />}
          onClick={() => setDrawerVisible(true)}
          style={{
            position: 'fixed',
            top: 16,
            left: 16,
            zIndex: 1000,
          }}
        />
      )}

      {/* 桌面端侧边栏 / 移动端抽屉 */}
      {isMobile ? (
        <Drawer
          placement="left"
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          width={200}
          bodyStyle={{ padding: 0 }}
        >
          <div style={{
            padding: '20px 16px 12px',
            borderBottom: '1px solid #f0f0f0',
          }}>
            <Title level={5} style={{ margin: 0, color: '#1890ff' }}>
              OpenHub
            </Title>
            <Text type="secondary" style={{ fontSize: 11 }}>管理后台</Text>
          </div>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            onClick={({ key }) => {
              setSelectedKey(key);
              setDrawerVisible(false);
            }}
            items={menuItems}
            style={{ border: 'none', marginTop: 8 }}
          />
          <div style={{ padding: '12px 16px', borderTop: '1px solid #f0f0f0' }}>
            <Button
              type="text"
              icon={<HomeOutlined />}
              onClick={() => navigate('/')}
              block
              style={{ textAlign: 'left', color: '#666' }}
            >
              返回首页
            </Button>
          </div>
        </Drawer>
      ) : (
        <Sider
          width={200}
          style={{
            background: '#fff',
            borderRight: '1px solid #f0f0f0',
            position: 'fixed',
            height: '100vh',
            left: 0,
            top: 0,
            bottom: 0,
            overflow: 'auto',
          }}
        >
          <div style={{
            padding: '20px 16px 12px',
            borderBottom: '1px solid #f0f0f0',
          }}>
            <Title level={5} style={{ margin: 0, color: '#1890ff' }}>
              OpenHub
            </Title>
            <Text type="secondary" style={{ fontSize: 11 }}>管理后台</Text>
          </div>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            onClick={({ key }) => setSelectedKey(key)}
            items={menuItems}
            style={{ border: 'none', marginTop: 8 }}
          />
          <div style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            padding: '12px 16px',
            borderTop: '1px solid #f0f0f0',
          }}>
            <Button
              type="text"
              icon={<HomeOutlined />}
              onClick={() => navigate('/')}
              block
              style={{ textAlign: 'left', color: '#666' }}
            >
              返回首页
            </Button>
          </div>
        </Sider>
      )}

      <Layout style={{ marginLeft: isMobile ? 0 : 200, background: '#f5f7fa' }}>
        <Content style={{ padding: isMobile ? '16px' : '24px 32px', minHeight: '100vh' }}>
          <Breadcrumb
            style={{ marginBottom: 16, marginTop: isMobile ? 48 : 0 }}
            items={[
              {
                title: (
                  <a onClick={() => navigate('/')}>
                    <HomeOutlined /> 首页
                  </a>
                ),
              },
              { title: '管理后台' },
            ]}
          />
          <Card bodyStyle={selectedKey === 'users' ? { padding: isMobile ? 12 : 24 } : undefined}>
            {renderContent()}
          </Card>
        </Content>
      </Layout>
    </Layout>
  );
};

export default AdminPage;
