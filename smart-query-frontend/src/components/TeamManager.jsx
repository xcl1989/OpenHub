import React, { useState, useEffect } from 'react';
import { Card, Button, Modal, Form, Input, Select, Tag, Space, Empty, Spin, message, Popconfirm } from 'antd';
import { PlusOutlined, DeleteOutlined, TeamOutlined, RobotOutlined } from '@ant-design/icons';
import { teamService, smartEntityService } from '../services/api';

const { TextArea } = Input;

function TeamManager({ isMobile }) {
  const [teams, setTeams] = useState([]);
  const [myEntities, setMyEntities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [createVisible, setCreateVisible] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [tRes, eRes] = await Promise.all([
        teamService.list(),
        smartEntityService.list(),
      ]);
      if (tRes.ok) setTeams(tRes.teams || []);
      if (eRes.ok) setMyEntities(eRes.my_entities || []);
    } catch {} finally {
      setLoading(false);
    }
  };

  const handleCreate = async (values) => {
    try {
      await teamService.create(values);
      message.success('团队创建成功');
      setCreateVisible(false);
      form.resetFields();
      fetchData();
    } catch (err) {
      message.error(err?.response?.data?.detail || '创建失败');
    }
  };

  const handleDelete = async (teamId) => {
    try {
      await teamService.delete(teamId);
      message.success('已删除');
      fetchData();
    } catch (err) {
      message.error('删除失败');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ fontWeight: 500 }}>智能体团队</span>
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
          创建团队
        </Button>
      </div>

      {loading ? (
        <Spin style={{ display: 'block', margin: '20px auto' }} />
      ) : teams.length === 0 ? (
        <Empty description="暂无团队，点击创建" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        teams.map(team => (
          <Card
            key={team.id}
            size="small"
            style={{ marginBottom: 12 }}
            title={<Space><TeamOutlined />{team.name}</Space>}
            extra={
              <Popconfirm title="确认删除？" onConfirm={() => handleDelete(team.id)}>
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            }
          >
            {team.description && <p style={{ color: '#666', fontSize: 12, marginBottom: 8 }}>{team.description}</p>}
            <Space size="small" wrap>
              <Tag color="gold">编排者: {team.orchestrator_entity_id}</Tag>
              {(Array.isArray(team.member_entity_ids) ? team.member_entity_ids : []).map((mid, i) => (
                <Tag key={i} icon={<RobotOutlined />} color="blue">{mid}</Tag>
              ))}
            </Space>
          </Card>
        ))
      )}

      <Modal
        title="创建智能体团队"
        open={createVisible}
        onCancel={() => setCreateVisible(false)}
        onOk={() => form.submit()}
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="团队名称" rules={[{ required: true }]}>
            <Input placeholder="如: 数据分析团队" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="团队的任务和协作方式" />
          </Form.Item>
          <Form.Item name="orchestrator_entity_id" label="编排者智能体" rules={[{ required: true, message: '请选择编排者' }]}>
            <Select placeholder="选择负责拆解和协调任务的智能体" showSearch optionFilterProp="label">
              {myEntities.map(e => (
                <Select.Option key={e.entity_id} value={e.entity_id} label={e.name}>
                  {e.name} <span style={{ color: '#999', fontSize: 11 }}>({e.base_agent})</span>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="member_entity_ids" label="成员智能体" rules={[{ required: true, type: 'array', min: 1, message: '至少选择一个成员' }]}>
            <Select mode="multiple" placeholder="选择团队成员" showSearch optionFilterProp="label">
              {myEntities.map(e => (
                <Select.Option key={e.entity_id} value={e.entity_id} label={e.name}>
                  {e.name} <span style={{ color: '#999', fontSize: 11 }}>({e.base_agent})</span>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default TeamManager;
