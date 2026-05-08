import React, { useState, useEffect, useCallback } from 'react';
import { Drawer, Button, Card, Tag, message, Modal, Form, Input, Select, Switch, Space, Collapse, Empty, Spin, Checkbox } from 'antd';
import { RobotOutlined, PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, TeamOutlined, ThunderboltOutlined, BarChartOutlined, SettingOutlined } from '@ant-design/icons';
import { smartEntityService, adminService } from '../services/api';
import EntityTestPanel from './EntityTestPanel';
import EntityMetricsPanel from './EntityMetricsPanel';
import TeamManager from './TeamManager';

const { TextArea } = Input;
const { Option } = Select;
const { Panel } = Collapse;

function SmartEntityManager({ open, onClose, isMobile }) {
  const width = isMobile ? '100%' : 800;
  const [loading, setLoading] = useState(false);
  const [myEntities, setMyEntities] = useState([]);
  const [discoverableEntities, setDiscoverableEntities] = useState([]);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingEntity, setEditingEntity] = useState(null);
  const [testPanelOpen, setTestPanelOpen] = useState(false);
  const [testEntity, setTestEntity] = useState(null);
  const [metricsPanelOpen, setMetricsPanelOpen] = useState(false);
  const [metricsEntity, setMetricsEntity] = useState(null);
  const [allModels, setAllModels] = useState([]);
  const [allTools, setAllTools] = useState([]);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();

  useEffect(() => {
    if (open) {
      fetchEntities();
      fetchModels();
      fetchTools();
    }
  }, [open]);

  const fetchEntities = async () => {
    setLoading(true);
    try {
      const result = await smartEntityService.list();
      setMyEntities(result.my_entities || []);
      setDiscoverableEntities(result.discoverable_entities || []);
    } catch {
      message.error('获取智能体列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchModels = async () => {
    try {
      const res = await adminService.getAllModels();
      if (res.success) setAllModels(res.data || []);
    } catch {}
  };

  const fetchTools = async () => {
    try {
      const res = await adminService.getTools();
      if (res.success) setAllTools(res.data || []);
    } catch {}
  };

  const handleCreate = async (values) => {
    try {
      const payload = { ...values };
      if (payload.model) {
        const [providerID, modelID] = payload.model.split('|', 2);
        payload.model = { providerID, modelID };
      }
      payload.discovery_config = { is_public: values.is_public || false };
      payload.collaboration_config = { auto_accept_tasks: values.auto_accept_tasks || false };
      payload.capabilities = payload.capabilities || [];
      delete payload.is_public;
      delete payload.auto_accept_tasks;
      await smartEntityService.create(payload);
      message.success('智能体创建成功');
      setCreateModalVisible(false);
      form.resetFields();
      fetchEntities();
    } catch (err) {
      message.error(err?.response?.data?.detail || '创建失败');
    }
  };

  const handleEdit = async (values) => {
    if (!editingEntity) return;
    try {
      const payload = { ...values };
      if (payload.model) {
        const [providerID, modelID] = payload.model.split('|', 2);
        payload.model = { providerID, modelID };
      }
      payload.discovery_config = { is_public: values.is_public || false };
      payload.collaboration_config = { auto_accept_tasks: values.auto_accept_tasks || false };
      payload.capabilities = payload.capabilities || [];
      delete payload.is_public;
      delete payload.auto_accept_tasks;
      await smartEntityService.update(editingEntity.entity_id, payload);
      message.success('更新成功');
      setEditModalVisible(false);
      setEditingEntity(null);
      editForm.resetFields();
      fetchEntities();
    } catch (err) {
      message.error(err?.response?.data?.detail || '更新失败');
    }
  };

  const handleDelete = async (entityId) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确定要继续吗？',
      onOk: async () => {
        try {
          await smartEntityService.delete(entityId);
          message.success('删除成功');
          fetchEntities();
        } catch (err) {
          message.error(err?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const openEditModal = (entity) => {
    setEditingEntity(entity);
    const dc = entity.discovery_config || {};
    const cc = entity.collaboration_config || {};
    editForm.setFieldsValue({
      name: entity.name,
      description: entity.description,
      base_agent: entity.base_agent,
      system_prompt: entity.system_prompt || '',
      model: entity.model
        ? `${entity.model.providerID}|${entity.model.modelID}`
        : undefined,
      is_public: dc.is_public || false,
      auto_accept_tasks: cc.auto_accept_tasks || false,
      tool_permissions: entity.tool_permissions || [],
    });
    setEditModalVisible(true);
  };

  const openTestPanel = (entity) => {
    setTestEntity(entity);
    setTestPanelOpen(true);
  };

  const openMetricsPanel = (entity) => {
    setMetricsEntity(entity);
    setMetricsPanelOpen(true);
  };

  const buildModelOption = (m) => ({
    label: `${m.name || m.modelID} (${m.providerName || m.providerID})`,
    value: `${m.providerID}|${m.modelID}`,
  });

  const entityForm = (formInstance, onFinish) => (
    <Form form={formInstance} layout="vertical" onFinish={onFinish}>
      <Form.Item name="entity_id" label="智能体ID"
        rules={[{ required: true, min: 3, message: '至少3个字符' }]}>
        <Input placeholder="如: data-analyst" disabled={!!editingEntity} />
      </Form.Item>
      <Form.Item name="name" label="显示名称"
        rules={[{ required: true, message: '请输入名称' }]}>
        <Input placeholder="如: 数据分析助手" />
      </Form.Item>
      <Form.Item name="description" label="描述"
        rules={[{ required: true, message: '请输入描述' }]}>
        <TextArea rows={2} placeholder="描述智能体的专长和使用场景" />
      </Form.Item>
      <Form.Item name="system_prompt" label="系统提示词">
        <TextArea rows={4} placeholder={"定义智能体的角色、行为规则、输出格式...\n\n示例：\n你是一个专业的数据分析师，擅长 SQL 查询和图表解读。\n- 收到数据后先做探索性分析\n- 用表格和图表展示结果\n- 给出可操作的业务建议"} />
      </Form.Item>
      <Form.Item name="base_agent" label="基础智能体" initialValue="build">
        <Select>
          <Option value="build">Build (通用构建)</Option>
          <Option value="plan">Plan (规划)</Option>
          <Option value="task">Task (任务)</Option>
        </Select>
      </Form.Item>
      <Form.Item name="model" label="专属模型">
        <Select placeholder="留空则使用全局默认模型" allowClear showSearch optionFilterProp="label">
          {allModels.map(m => (
            <Option key={`${m.providerID}|${m.modelID}`} value={`${m.providerID}|${m.modelID}`} label={m.name || m.modelID}>
              {m.name || m.modelID} <span style={{ color: '#999', fontSize: 11 }}>{m.providerName || m.providerID}</span>
            </Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item name="tool_permissions" label="工具权限" valuePropName="value" initialValue={[]}
        getValueFromEvent={(v) => v}
        trigger="onChange">
        <Select mode="multiple" placeholder="选择允许使用的工具" allowClear>
          {allTools.map(t => (
            <Option key={t.tool_name} value={t.tool_name}>
              <Space><span>{t.tool_name}</span><Tag color={t.risk_level === 'dangerous' ? 'red' : t.risk_level === 'moderate' ? 'orange' : 'green'} style={{ fontSize: 10 }}>{t.risk_level}</Tag></Space>
            </Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item name="is_public" valuePropName="checked" initialValue={false}>
        <Switch checkedChildren="组织内可见" unCheckedChildren="仅自己可见" />
      </Form.Item>
      <Form.Item name="auto_accept_tasks" valuePropName="checked" initialValue={false}>
        <Switch checkedChildren="自动接受任务" unCheckedChildren="手动确认" />
      </Form.Item>
    </Form>
  );

  const renderEntityCard = (entity, isMine = true) => (
    <Card
      key={entity.entity_id}
      size="small"
      style={{ marginBottom: 12 }}
      title={
        <Space>
          <RobotOutlined />
          <span>{entity.name}</span>
          <Tag color={entity.status === 'active' ? 'green' : 'default'}>
            {entity.status === 'active' ? '活跃' : '停用'}
          </Tag>
        </Space>
      }
      extra={
        isMine ? (
          <Space size="small" wrap>
            <Button size="small" icon={<ThunderboltOutlined />} onClick={() => openTestPanel(entity)}>测试</Button>
            <Button size="small" icon={<BarChartOutlined />} onClick={() => openMetricsPanel(entity)}>数据</Button>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(entity)}>编辑</Button>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(entity.entity_id)}>删除</Button>
          </Space>
        ) : (
          <Button size="small" icon={<EyeOutlined />}>查看</Button>
        )
      }
    >
      <p style={{ color: '#666', fontSize: 13, marginBottom: 8 }}>{entity.description}</p>
      {entity.system_prompt && (
        <p style={{ color: '#999', fontSize: 12, marginBottom: 8, maxHeight: 40, overflow: 'hidden', textOverflow: 'ellipsis' }}>
          System: {entity.system_prompt.substring(0, 60)}{entity.system_prompt.length > 60 ? '...' : ''}
        </p>
      )}
      <Space size="small" wrap>
        <Tag>基础: {entity.base_agent}</Tag>
        {entity.model && (
          <Tag color="purple">{entity.model.modelID || JSON.stringify(entity.model).substring(0, 20)}</Tag>
        )}
        {(entity.capabilities || []).map((cap, i) => (
          <Tag key={i} color="blue">{cap.name || cap}</Tag>
        ))}
        {(entity.tool_permissions || []).slice(0, 3).map((t, i) => (
          <Tag key={i} color="cyan"><SettingOutlined /> {t}</Tag>
        ))}
        {(entity.tool_permissions || []).length > 3 && (
          <Tag>+{entity.tool_permissions.length - 3}</Tag>
        )}
      </Space>
    </Card>
  );

  const createFormContent = entityForm(form, handleCreate);
  const editFormContent = entityForm(editForm, handleEdit);

  return (
    <>
      <Drawer
        title={<div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><RobotOutlined /><span>智能体管理</span></div>}
        placement="right"
        width={width}
        onClose={onClose}
        open={open}
        mask={false}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setCreateModalVisible(true); }}>
            创建智能体
          </Button>
        }
      >
        {loading ? (
          <Spin style={{ display: 'block', margin: '40px auto' }} />
        ) : (
          <Collapse defaultActiveKey={['my', 'discoverable']}>
            <Panel header={`我的智能体 (${myEntities.length})`} key="my">
              {myEntities.length === 0 ? (
                <Empty description="暂无智能体，点击右上角创建" />
              ) : (
                myEntities.map(e => renderEntityCard(e, true))
              )}
            </Panel>
            <Panel header={<Space><TeamOutlined />组织内可发现 ({discoverableEntities.length})</Space>} key="discoverable">
              {discoverableEntities.length === 0 ? (
                <Empty description="暂无可发现的智能体" />
              ) : (
                discoverableEntities.map(e => renderEntityCard(e, false))
              )}
            </Panel>
            <Panel header={<Space><TeamOutlined />智能体团队</Space>} key="teams">
              <TeamManager isMobile={isMobile} />
            </Panel>
          </Collapse>
        )}
      </Drawer>

      <Modal title="创建智能体" open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        onOk={() => form.submit()} width={640} destroyOnClose>
        {createFormContent}
      </Modal>

      <Modal title={`编辑 - ${editingEntity?.name || ''}`} open={editModalVisible}
        onCancel={() => { setEditModalVisible(false); setEditingEntity(null); editForm.resetFields(); }}
        onOk={() => editForm.submit()} width={640} destroyOnClose>
        {editFormContent}
      </Modal>

      {testEntity && (
        <EntityTestPanel
          open={testPanelOpen}
          onClose={() => setTestPanelOpen(false)}
          entity={testEntity}
          isMobile={isMobile}
        />
      )}

      {metricsEntity && (
        <EntityMetricsPanel
          open={metricsPanelOpen}
          onClose={() => setMetricsPanelOpen(false)}
          entityId={metricsEntity.entity_id}
          entityName={metricsEntity.name}
          isMobile={isMobile}
        />
      )}
    </>
  );
}

export default SmartEntityManager;
