import React, { useState, useEffect } from 'react';
import { Drawer, Tabs, Spin, message, Typography, Alert, Space } from 'antd';
import { BookOutlined, UserOutlined } from '@ant-design/icons';
import { memoryService } from '../services/api';
import MarkdownRenderer from './MarkdownRenderer';

const { Text, Title } = Typography;

function MemoryViewer({ open, onClose, isMobile }) {
  const width = isMobile ? '100%' : 720;
  const [loading, setLoading] = useState(false);
  const [memory, setMemory] = useState({ facts: '', preferences: '' });

  useEffect(() => {
    if (open) {
      fetchMemory();
    }
  }, [open]);

  const fetchMemory = async () => {
    setLoading(true);
    try {
      const result = await memoryService.getMemory();
      setMemory({ facts: result.facts || '', preferences: result.preferences || '' });
    } catch {
      message.error('获取记忆失败');
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'facts',
      label: (
        <span>
          <BookOutlined />
          事实记忆
        </span>
      ),
      children: (
        <div style={{ padding: '8px 0' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Spin />
            </div>
          ) : memory.facts ? (
            <MarkdownRenderer content={memory.facts} />
          ) : (
            <Alert
              message="暂无事实记忆"
              description="AI 会在认为重要信息值得记住时自动保存到 MEMORY.md"
              type="info"
              showIcon
            />
          )}
        </div>
      ),
    },
    {
      key: 'preferences',
      label: (
        <span>
          <UserOutlined />
          用户偏好
        </span>
      ),
      children: (
        <div style={{ padding: '8px 0' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Spin />
            </div>
          ) : memory.preferences ? (
            <MarkdownRenderer content={memory.preferences} />
          ) : (
            <Alert
              message="暂无用户偏好"
              description="AI 会在了解您的偏好后自动保存到 USER.md"
              type="info"
              showIcon
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <Drawer
      title={
        <Space>
          <BookOutlined />
          <span>跨会话记忆</span>
        </Space>
      }
      placement="right"
      width={width}
      onClose={onClose}
      open={open}
      mask={false}
    >
      <Tabs defaultActiveKey="facts" items={tabItems} />
      <div style={{ marginTop: 16, padding: '12px', background: '#f5f5f5', borderRadius: 6 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          记忆由 AI 自动管理，您可以查看但不能直接编辑。如需修改记忆，请告诉 AI "更新我的记忆"。
        </Text>
      </div>
    </Drawer>
  );
}

export default MemoryViewer;
