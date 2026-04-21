import React, { useState, useEffect } from 'react';
import { Drawer, Button, Card, List, Tag, message, Modal, Form, Input, Select, Switch, Space, Collapse, Empty, Spin } from 'antd';
import { RobotOutlined, PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, TeamOutlined } from '@ant-design/icons';
import { smartEntityService } from '../services/api';

const { TextArea } = Input;
const { Option } = Select;
const { Panel } = Collapse;

function SmartEntityManager({ open, onClose, isMobile }) {
  const width = isMobile ? '100%' : 800;
  const [loading, setLoading] = useState(false);
  const [myEntities, setMyEntities] = useState([]);
  const [discoverableEntities, setDiscoverableEntities] = useState([]);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    if (open) {
      fetchEntities();
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

  const handleCreate = async (values) => {
    try {
      await smartEntityService.create(values);
      message.success('智能体创建成功');
      setCreateModalVisible(false);
      form.resetFields();
      fetchEntities();
    } catch (err) {
      message.error(err?.response?.data?.detail || '创建失败');
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
          <Space>
            <Button type="link" size="small" icon={<EditOutlined />}>编辑</Button>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(entity.entity_id)}>删除</Button>
          </Space>
        ) : (
          <Button type="link" size="small" icon={<EyeOutlined />}>查看</Button>
        )
      }
    >
      <p style={{ color: '#666', fontSize: 13 }}>{entity.description}</p>
      <Space size="small" wrap>
        <Tag>基础: {entity.base_agent}</Tag>
        {entity.capabilities && JSON.parse(entity.capabilities || '[]').map((cap, i) => (
          <Tag key={i} color="blue">{cap.name}</Tag>
        ))}
      </Space>
    </Card>
  );

  return (
    <>
      <Drawer
        title={<Space><RobotOutlined /><span>智能体管理</span></Space>}
        placement="right"
        width={width}
        onClose={onClose}
        open={open}
        mask={false}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
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
          </Collapse>
        )}
      </Drawer>

      <Modal
        title="创建智能体"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="entity_id"
            label="智能体ID"
            rules={[{ required: true, min: 3, message: '至少3个字符' }]}
          >
            <Input placeholder="如: data-analyst" />
          </Form.Item>
          <Form.Item
            name="name"
            label="显示名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="如: 数据分析助手" />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
            rules={[{ required: true, message: '请输入描述' }]}
          >
            <TextArea rows={3} placeholder="描述智能体的专长和使用场景" />
          </Form.Item>
          <Form.Item name="base_agent" label="基础智能体" initialValue="build">
            <Select>
              <Option value="build">Build (通用构建)</Option>
              <Option value="plan">Plan (规划)</Option>
              <Option value="task">Task (任务)</Option>
            </Select>
          </Form.Item>
          <Form.Item name="discovery_config" label="可发现性">
            <Form.Item name={['discovery_config', 'is_public']} valuePropName="checked" noStyle initialValue={false}>
              <Switch checkedChildren="组织内可见" unCheckedChildren="仅自己可见" />
            </Form.Item>
          </Form.Item>
          <Form.Item name="collaboration_config" label="协作模式">
            <Form.Item name={['collaboration_config', 'auto_accept_tasks']} valuePropName="checked" noStyle initialValue={false}>
              <Switch checkedChildren="自动接受任务" unCheckedChildren="手动确认" />
            </Form.Item>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default SmartEntityManager;
