import React from 'react';
import { Space, Card, Avatar, Typography, Spin, Tag } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import MarkdownRenderer from './MarkdownRenderer';
import ToolCall from './ToolCall';
import QuestionFormInline from './QuestionFormInline';

const AssistantMessage = ({ message, filterContent, messageTimings, handleQuestionSubmit, pendingQuestionIdRef, formatDuration, idleState, lastAssistantMessageId }) => {
  return (
    <div
      className="message-item-assistant"
      style={{
        display: 'flex',
        justifyContent: 'flex-start',
        animation: 'fadeIn 0.3s ease-in',
        width: '100%'
      }}
    >
      <Space align="start" className="message-space" style={{ maxWidth: 'min(92vw, 1000px)', gap: 8 }}>
        <Avatar 
          style={{ 
            background: '#1890ff',
            flexShrink: 0,
            minWidth: '36px'
          }}
          size={36}
          icon={<QuestionCircleOutlined />}
        />
        <Card
          className="message-bubble"
          style={{
            borderRadius: 12,
            borderTopLeftRadius: 4,
            background: '#ffffff',
            color: '#000',
            boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
            border: '1px solid #e5e7eb',
            maxWidth: 'min(85vw, 800px)',
            width: message.content ? Math.min(Math.max(message.content.length * 9 + 50, 200), 800) : 'auto'
          }}
          size="small"
          styles={{ body: { padding: '12px 14px' } }}
        >
          <>
              {message.reasoning && (
                <div style={{ 
                  marginBottom: 4, 
                  padding: '8px 10px',
                  background: '#f9fafb',
                  borderRadius: 6,
                  borderLeft: '2px solid #1890ff'
                }}>
                  <div style={{ 
                    fontSize: 11, 
                    color: '#6b7280', 
                    fontWeight: 600,
                    marginBottom: 4,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px'
                  }}>
                    分析过程
                  </div>
                  <div style={{ 
                    fontSize: 13, 
                    color: '#374151',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.6
                  }}>
                    {message.reasoning}
                  </div>
                </div>
              )}
              <div className="markdown-content" style={{ 
                fontSize: 15,
                lineHeight: 1.6,
                color: '#1f2937'
              }}>
                <MarkdownRenderer content={filterContent(message.content, message.reasoning)} />
              </div>
              {message.tools && Object.entries(message.tools).map(([key, tool]) => {
                const inputData = typeof tool.input === 'string' 
                  ? (() => {
                      try {
                        return JSON.parse(tool.input);
                      } catch {
                        return tool.input;
                      }
                    })()
                  : tool.input;
                
                const questions = inputData?.questions || tool.questions || [];
                
                if (tool.tool === 'question' && questions.length > 0 && (tool.state === 'running' || tool.state === 'error' || !tool.state)) {
                  return (
                    <div
                      key={key}
                      style={{
                        marginTop: 16,
                        padding: '16px',
                        background: '#f9fafb',
                        borderRadius: 8,
                        border: '1px solid #e5e7eb'
                      }}
                    >
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginBottom: 16,
                        paddingBottom: 12,
                        borderBottom: '1px solid #e5e7eb'
                      }}>
                        <QuestionCircleOutlined style={{ color: '#1890ff', fontSize: 18 }} />
                        <span style={{ 
                          fontWeight: 600, 
                          fontSize: 13,
                          color: '#1f2937'
                        }}>
                          需要您填写以下信息
                        </span>
                      </div>
                      <QuestionFormInline
                        questions={questions}
                        onSubmit={(answers) => handleQuestionSubmit(answers, key)}
                        onCancel={() => {}}
                      />
                    </div>
                  );
                }
                
                return <ToolCall key={key} tool={tool} />;
              })}
              {message.streaming && !idleState && (
                <Spin size="small" style={{ marginLeft: 8 }} />
              )}
              <div style={{ 
                marginTop: 12,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                flexWrap: 'wrap'
              }}>
                <div style={{ 
                  fontSize: 11, 
                  color: '#9ca3af',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}>
                  {message.timestamp.toLocaleString('zh-CN', { 
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false
                  }).replace(/\//g, '-')}
                   {message.type === 'assistant' && 
                    messageTimings[message.id] && 
                    !message.streaming &&
                    message.id === lastAssistantMessageId && (
                     <span style={{
                       fontSize: 10,
                       color: '#1890ff',
                       fontWeight: 500
                     }}>
                       · 耗时 {formatDuration(messageTimings[message.id])}
                     </span>
                   )}
                </div>
                {message.type === 'assistant' && (
                  <Tag 
                    style={{ 
                      fontSize: 10,
                      background: '#f3f4f6',
                      color: '#6b7280',
                      border: '1px solid #e5e7eb',
                      borderRadius: 4,
                      padding: '2px 8px'
                    }}
                  >
                    由 OpenHub 大模型生成
                  </Tag>
                )}
              </div>
          </>
        </Card>
      </Space>
    </div>
  );
};

export default AssistantMessage;
