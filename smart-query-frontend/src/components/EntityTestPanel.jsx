import React, { useState, useRef, useEffect } from 'react';
import { Drawer, Input, Button, Space, Spin, Typography, Empty, Tag } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons';
import { smartEntityService } from '../services/api';

const { Text, Paragraph } = Typography;

function EntityTestPanel({ open, onClose, entity, isMobile }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (open) {
      setMessages([{
        role: 'system',
        content: `开始测试智能体「${entity.name}」。输入消息查看回复。`,
      }]);
      setInput('');
    }
  }, [open, entity]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);
    try {
      const result = await smartEntityService.test(entity.entity_id, text);
      if (result.ok) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: result.reply || '(空回复)',
          reasoning: result.reasoning || '',
          message_count: result.message_count,
        }]);
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `错误: ${result.error || '未知错误'}`,
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `请求失败: ${err.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer
      title={<Space><RobotOutlined />测试: {entity.name}</Space>}
      placement="right"
      width={isMobile ? '100%' : 500}
      onClose={onClose}
      open={open}
      mask={false}
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
        <div style={{ flex: 1, overflow: 'auto', marginBottom: 12 }}>
          {messages.map((msg, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              {msg.role === 'system' ? (
                <div style={{ textAlign: 'center', color: '#999', fontSize: 12, padding: '8px 0' }}>
                  {msg.content}
                </div>
              ) : msg.role === 'user' ? (
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <div style={{
                    maxWidth: '80%', background: '#1890ff', color: '#fff',
                    padding: '8px 12px', borderRadius: 12, fontSize: 14,
                  }}>
                    {msg.content}
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ marginBottom: 4 }}>
                    <Tag color="green" icon={<RobotOutlined />}>{entity.name}</Tag>
                  </div>
                  {msg.reasoning && (
                    <div style={{
                      background: '#fafafa', padding: '8px 12px', borderRadius: 8,
                      marginBottom: 8, fontSize: 12, color: '#888', maxHeight: 120, overflow: 'auto',
                    }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>思考过程:</Text>
                      <Paragraph style={{ marginBottom: 0, fontSize: 12 }}>{msg.reasoning}</Paragraph>
                    </div>
                  )}
                  <div style={{
                    background: '#f0f5ff', padding: '8px 12px', borderRadius: 12,
                    fontSize: 14, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}>
                    {msg.content}
                  </div>
                </div>
              )}
            </div>
          ))}
          {messages.length === 0 && <Empty description="输入消息开始测试" />}
          <div ref={messagesEndRef} />
        </div>

        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={input}
            onChange={e => setInput(e.target.value)}
            onPressEnter={handleSend}
            placeholder="输入测试消息..."
            disabled={loading}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={loading}>
            发送
          </Button>
        </Space.Compact>
      </div>
    </Drawer>
  );
}

export default EntityTestPanel;
