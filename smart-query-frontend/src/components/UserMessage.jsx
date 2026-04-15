import React from 'react';
import { Space, Card, Avatar, Image, Spin, Typography, Tag } from 'antd';
import { UserOutlined } from '@ant-design/icons';

const { Text } = Typography;

const AGENT_COLORS = {
  build: { bg: '#1890ff', shadow: 'rgba(24,144,255,0.3)', tag: 'blue' },
  plan: { bg: '#722ed1', shadow: 'rgba(114,46,209,0.3)', tag: 'purple' },
};

const UserMessage = ({ message }) => {
  const agentConfig = AGENT_COLORS[message.agent] || AGENT_COLORS.build;
  const estimatedBubbleWidth = message.content 
    ? Math.min(Math.max(message.content.length * 9 + 50, 150), 500)
    : 200;

  return (
    <div
      className="message-item-user"
      style={{
        display: 'flex',
        justifyContent: 'flex-end',
        animation: 'fadeIn 0.3s ease-in',
        width: '100%'
      }}
    >
      <Space align="end" className="message-space" style={{ maxWidth: 'min(92vw, 500px)', gap: 8 }}>
        <Card
          className="message-bubble"
          style={{
            borderRadius: 12,
            borderTopRightRadius: 4,
            background: agentConfig.bg,
            color: '#fff',
            boxShadow: `0 2px 8px ${agentConfig.shadow}`,
            border: 'none',
            maxWidth: 'min(85vw, 500px)',
            width: Math.min(estimatedBubbleWidth, 500)
          }}
          size="small"
          styles={{ body: { padding: '12px 14px' } }}
        >
          <div style={{ 
            width: '100%',
            fontSize: 15,
            lineHeight: 1.6
          }}>
            {message.images && message.images.length > 0 && (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
                gap: 8,
                maxWidth: '100%',
                marginBottom: 4
              }}>
                {message.images.map((img, idx) => (
                  <div
                    key={idx}
                    style={{
                      width: '100%',
                      aspectRatio: '1',
                      borderRadius: 8,
                      border: '2px solid rgba(255,255,255,0.3)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(255,255,255,0.1)',
                      overflow: 'hidden'
                    }}
                  >
                    {img.loading ? (
                      <Spin size="small" style={{ color: '#fff' }} />
                    ) : img.error ? (
                      <div style={{ 
                        color: 'rgba(255,255,255,0.7)', 
                        fontSize: 11,
                        textAlign: 'center',
                        padding: 4
                      }}>
                        失败
                      </div>
                    ) : img.base64 && img.type ? (
                      <Image 
                        src={`data:${img.type};base64,${img.base64}`}
                        alt={img.name || 'image'}
                        style={{
                          width: '100%',
                          height: '100%',
                          objectFit: 'cover',
                          cursor: 'pointer'
                        }}
                        preview={{ mask: false }}
                      />
                    ) : (
                      <div style={{ 
                        color: 'rgba(255,255,255,0.5)', 
                        fontSize: 10,
                        textAlign: 'center',
                        padding: 4
                      }}>
                        加载中...
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            {message.content && (
              <Text style={{ 
                color: '#fff',
                whiteSpace: 'pre-wrap',
                fontSize: 15,
                maxWidth: '100%',
                wordBreak: 'break-word'
              }}>
                {message.content}
              </Text>
            )}
          </div>
          <div style={{ 
            marginTop: 8,
            paddingTop: 8,
            borderTop: '1px solid rgba(255,255,255,0.2)',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            gap: 8,
            fontSize: 11,
            color: 'rgba(255,255,255,0.7)'
          }}>
            <Tag color={agentConfig.tag} style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: 0, border: 'none' }}>
              {message.agent === 'plan' ? 'Plan' : 'Build'}
            </Tag>
            {message.model && (
              <Tag style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: 0, background: 'rgba(255,255,255,0.2)', color: 'rgba(255,255,255,0.85)', border: 'none' }}>
                {typeof message.model === 'object' ? message.model.modelID : message.model}
              </Tag>
            )}
            <span>
              {message.timestamp.toLocaleString('zh-CN', { 
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
              }).replace(/\//g, '-')}
            </span>
          </div>
        </Card>
        <Avatar 
          style={{ 
            background: '#10b981',
            flexShrink: 0,
            minWidth: '36px'
          }}
          size={36}
          icon={<UserOutlined />}
        />
      </Space>
    </div>
  );
};

export default UserMessage;
