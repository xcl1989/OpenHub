import React, { useState, useEffect } from 'react';
import {
  Drawer, Table, Button, Space, Input, Modal, Form, Tag, Spin, message,
  Typography, Popconfirm, Empty, Tabs, Upload, Tooltip, Badge, Card
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, SearchOutlined,
  UploadOutlined, BookOutlined, FileTextOutlined, DatabaseOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { knowledgeService, adminKnowledgeService } from '../services/api';

const { Text, Title } = Typography;
const { TextArea } = Input;

function KnowledgeManager({ open, onClose, isMobile }) {
  const width = isMobile ? '100%' : 780;
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingSource, setEditingSource] = useState(null);
  const [stats, setStats] = useState({ total_sources: 0, total_chars: 0 });
  const [enterpriseSources, setEnterpriseSources] = useState([]);
  const [enterpriseLoading, setEnterpriseLoading] = useState(false);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();

  useEffect(() => {
    if (open) {
      fetchSources();
      fetchStats();
      fetchEnterpriseSources();
    }
  }, [open]);

  const fetchSources = async () => {
    setLoading(true);
    try {
      const result = await knowledgeService.listSources();
      if (result.ok) {
        setSources(result.sources || []);
      }
    } catch {
      message.error('获取知识库失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const result = await knowledgeService.getStats();
      if (result.ok) {
        setStats(result.stats);
      }
    } catch {}
  };

  const fetchEnterpriseSources = async () => {
    setEnterpriseLoading(true);
    try {
      const result = await adminKnowledgeService.listBases();
      if (result.ok && result.kbs?.length > 0) {
        const allSources = [];
        for (const kb of result.kbs) {
          const srcResult = await adminKnowledgeService.listSources(kb.id);
          if (srcResult.ok) {
            for (const s of (srcResult.sources || [])) {
              allSources.push({ ...s, kb_name: kb.name });
            }
          }
        }
        setEnterpriseSources(allSources);
      } else {
        setEnterpriseSources([]);
      }
    } catch {
      setEnterpriseSources([]);
    } finally {
      setEnterpriseLoading(false);
    }
  };

  const handleAdd = async () => {
    try {
      const values = await form.validateFields();
      const result = await knowledgeService.createSource(values);
      if (result.ok) {
        message.success('添加成功');
        setAddModalOpen(false);
        form.resetFields();
        fetchSources();
        fetchStats();
      }
    } catch (err) {
      if (err.response) {
        message.error(err.response.data?.detail || '添加失败');
      }
    }
  };

  const handleUpload = async (file) => {
    const title = file.name.replace(/\.[^.]+$/, '');
    try {
      const result = await knowledgeService.uploadSource(title, file);
      if (result.ok) {
        message.success('上传解析成功');
        fetchSources();
        fetchStats();
      }
    } catch (err) {
      message.error(err.response?.data?.detail || '上传失败');
    }
    return false;
  };

  const handleEdit = async () => {
    try {
      const values = await editForm.validateFields();
      const result = await knowledgeService.updateSource(editingSource.id, values);
      if (result.ok) {
        message.success('更新成功');
        setEditModalOpen(false);
        setEditingSource(null);
        editForm.resetFields();
        fetchSources();
        fetchStats();
      }
    } catch (err) {
      if (err.response) {
        message.error(err.response?.data?.detail || '更新失败');
      }
    }
  };

  const handleDelete = async (sourceId) => {
    try {
      await knowledgeService.deleteSource(sourceId);
      message.success('已删除');
      fetchSources();
      fetchStats();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSearch = async () => {
    if (!searchText.trim()) {
      setSearchResults(null);
      return;
    }
    try {
      const result = await knowledgeService.search(searchText);
      if (result.ok) {
        setSearchResults(result.results || []);
      }
    } catch {
      message.error('搜索失败');
    }
  };

  const openEditModal = (record) => {
    setEditingSource(record);
    editForm.setFieldsValue({
      title: record.title,
      content: record.content,
      tags: record.tags ? record.tags.join(', ') : '',
    });
    setEditModalOpen(true);
  };

  const displaySources = searchResults !== null ? searchResults : sources;

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text, record) => (
        <Space>
          <FileTextOutlined />
          <Text strong>{text}</Text>
          {record.source_type !== 'markdown' && (
            <Tag color="blue">{record.source_type}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '字符数',
      dataIndex: 'char_count',
      key: 'char_count',
      width: 90,
      render: (v) => <Text type="secondary">{v?.toLocaleString()}</Text>,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 150,
      render: (tags) =>
        tags?.length > 0
          ? tags.map((t, i) => <Tag key={i}>{t}</Tag>)
          : <Text type="secondary">-</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Space>
          <Tooltip title="编辑">
            <Button type="text" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          </Tooltip>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'list',
      label: (
        <span>
          <DatabaseOutlined />
          知识列表
          <Badge count={stats.total_sources} size="small" style={{ marginLeft: 6 }} />
        </span>
      ),
      children: (
        <div>
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
            <Space>
              <Input.Search
                placeholder="搜索知识..."
                value={searchText}
                onChange={(e) => {
                  setSearchText(e.target.value);
                  if (!e.target.value.trim()) setSearchResults(null);
                }}
                onSearch={handleSearch}
                style={{ width: isMobile ? 160 : 240 }}
                allowClear
              />
            </Space>
            <Space>
              <Upload
                beforeUpload={handleUpload}
                showUploadList={false}
                accept=".md,.txt,.pdf,.docx,.xlsx,.csv"
              >
                <Button icon={<UploadOutlined />}>上传文件</Button>
              </Upload>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddModalOpen(true)}>
                添加
              </Button>
            </Space>
          </div>
          <Table
            dataSource={displaySources}
            columns={columns}
            rowKey="id"
            loading={loading}
            size="small"
            pagination={{ pageSize: 10, size: 'small' }}
            locale={{ emptyText: <Empty description="暂无知识，点击添加或上传文件" /> }}
          />
        </div>
      ),
    },
    {
      key: 'stats',
      label: <span><BookOutlined /> 统计</span>,
      children: (
        <div style={{ padding: '16px 0' }}>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Card size="small">
              <Space>
                <Text type="secondary">知识条目数：</Text>
                <Text strong>{stats.total_sources}</Text>
              </Space>
            </Card>
            <Card size="small">
              <Space>
                <Text type="secondary">总字符数：</Text>
                <Text strong>{stats.total_chars?.toLocaleString()}</Text>
              </Space>
            </Card>
            <div style={{ marginTop: 8, padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                知识库内容会在提问时自动注入到上下文中。小型知识库全量注入，大型知识库按搜索结果注入。
                企业知识库始终以搜索检索方式注入。
              </Text>
            </div>
          </Space>
        </div>
      ),
    },
    {
      key: 'enterprise',
      label: (
        <span>
          <LockOutlined />
          企业知识
          <Badge count={enterpriseSources.length} size="small" style={{ marginLeft: 6 }} />
        </span>
      ),
      children: (
        <div>
          <div style={{ marginBottom: 12, padding: '8px 12px', background: '#f0f5ff', borderRadius: 6 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <LockOutlined /> 企业知识库由管理员维护，所有用户可查询但不可编辑。提问时会自动检索相关内容。
            </Text>
          </div>
          <Table
            dataSource={enterpriseSources}
            columns={[
              {
                title: '标题',
                dataIndex: 'title',
                key: 'title',
                ellipsis: true,
                render: (text) => (
                  <Space>
                    <FileTextOutlined />
                    <Text strong>{text}</Text>
                  </Space>
                ),
              },
              {
                title: '来源',
                dataIndex: 'kb_name',
                key: 'kb_name',
                width: 150,
                render: (text) => <Tag color="blue">{text}</Tag>,
              },
              {
                title: '字符数',
                dataIndex: 'char_count',
                key: 'char_count',
                width: 80,
                render: (v) => <Text type="secondary">{v?.toLocaleString()}</Text>,
              },
            ]}
            rowKey="id"
            loading={enterpriseLoading}
            size="small"
            pagination={{ pageSize: 10, size: 'small' }}
            locale={{ emptyText: <Empty description="暂无企业知识库内容" /> }}
          />
        </div>
      ),
    },
  ];

  return (
    <>
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <BookOutlined />
            <span>知识库管理</span>
          </div>
        }
        placement="right"
        width={width}
        onClose={onClose}
        open={open}
        mask={false}
      >
        <Tabs defaultActiveKey="list" items={tabItems} />
      </Drawer>

      <Modal
        title="添加知识"
        open={addModalOpen}
        onOk={handleAdd}
        onCancel={() => { setAddModalOpen(false); form.resetFields(); }}
        width={isMobile ? '95%' : 600}
        okText="添加"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="知识标题" />
          </Form.Item>
          <Form.Item name="tags" label="标签（逗号分隔）">
            <Input placeholder="如: API, 文档, Python" />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true, message: '请输入内容' }]}>
            <TextArea rows={12} placeholder="支持 Markdown 格式" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="编辑知识"
        open={editModalOpen}
        onOk={handleEdit}
        onCancel={() => { setEditModalOpen(false); setEditingSource(null); editForm.resetFields(); }}
        width={isMobile ? '95%' : 600}
        okText="保存"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="tags" label="标签（逗号分隔）">
            <Input placeholder="如: API, 文档, Python" />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true, message: '请输入内容' }]}>
            <TextArea rows={12} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default KnowledgeManager;
