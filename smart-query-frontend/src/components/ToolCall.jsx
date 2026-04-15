import React, { useState } from 'react';
import { Tag } from 'antd';
import { CheckCircleOutlined, LoadingOutlined, QuestionCircleOutlined } from '@ant-design/icons';

const ToolCall = ({ tool }) => {
  const [collapsed, setCollapsed] = useState(true);
  
  const inputData = typeof tool.input === 'string' 
    ? (() => {
        try {
          return JSON.parse(tool.input);
        } catch {
          return { raw: tool.input };
        }
      })()
    : tool.input;
  
  const questions = inputData?.questions || tool.questions || [];
  const hasQuestions = questions.length > 0;
  
  const getToolIcon = () => {
    if (tool.state === 'completed') return <CheckCircleOutlined style={{ color: '#059669', fontSize: 16 }} />;
    if (tool.state === 'error') return <QuestionCircleOutlined style={{ color: '#dc2626', fontSize: 16 }} />;
    if (tool.state === 'running') return <LoadingOutlined style={{ color: '#2563eb', fontSize: 16 }} />;
    return <QuestionCircleOutlined />;
  };
  
  const getToolColor = () => {
    if (tool.state === 'completed') return 'green';
    if (tool.state === 'error') return 'red';
    if (tool.state === 'running') return 'blue';
    return 'default';
  };
  
  const getToolBg = () => {
    if (tool.state === 'completed') return '#f0f9ff';
    if (tool.state === 'error') return '#fff1f2';
    if (tool.state === 'running') return '#eff6ff';
    return '#f9fafb';
  };
  
  const getToolBorder = () => {
    if (tool.state === 'completed') return '#bae6fd';
    if (tool.state === 'error') return '#fecdd3';
    if (tool.state === 'running') return '#bfdbfe';
    return '#e5e7eb';
  };
  
  return (
    <div
      style={{
        marginTop: 12,
        borderRadius: 8,
        border: '1px solid ' + getToolBorder(),
        overflow: 'hidden'
      }}
    >
      {/* 折叠头部 - 始终显示 */}
      <div 
        onClick={() => setCollapsed(!collapsed)}
        style={{
          padding: '10px 14px',
          background: getToolBg(),
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          transition: 'background-color 0.2s',
          userSelect: 'none'
        }}
        onMouseEnter={(e) => {
          if (collapsed) {
            e.currentTarget.style.background = tool.state === 'completed' ? '#e0f2fe' :
                                               tool.state === 'error' ? '#ffe4e6' :
                                               tool.state === 'running' ? '#dbeafe' : '#f3f4f6';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = getToolBg();
        }}
      >
        {getToolIcon()}
        <span style={{ 
          fontWeight: 600, 
          fontSize: 13,
          color: '#1f2937',
          textTransform: 'capitalize'
        }}>
          {tool.tool}
        </span>
        <Tag 
          color={getToolColor()}
          style={{ 
            fontSize: 11,
            borderRadius: 4,
            padding: '2px 8px'
          }}
        >
          {tool.state || 'pending'}
        </Tag>
        <span style={{ 
          marginLeft: 'auto', 
          fontSize: 12, 
          color: '#6b7280',
          transition: 'transform 0.2s',
          transform: collapsed ? 'rotate(0deg)' : 'rotate(180deg)'
        }}>
          {collapsed ? '▶' : '▼'}
        </span>
      </div>
      
      {/* 展开内容 - 折叠时隐藏 */}
      {!collapsed && (
        <div style={{
          padding: '12px 14px',
          background: '#ffffff',
          borderTop: '1px solid ' + getToolBorder()
        }}>
          {/* 输入区域 */}
          {tool.input && (
            <div style={{ 
              marginBottom: 12,
              padding: '10px 12px',
              background: '#f9fafb',
              borderRadius: 6,
              border: '1px solid #e5e7eb'
            }}>
              <div style={{ 
                fontSize: 11, 
                color: '#9ca3af', 
                marginBottom: 8,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                输入参数
              </div>
              {hasQuestions ? (
                <div style={{ 
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6
                }}>
                  {questions.map((q, i) => (
                    <div key={i} style={{ 
                      padding: '8px 10px',
                      background: '#ffffff',
                      borderRadius: 4,
                      border: '1px solid #e5e7eb'
                    }}>
                      <div style={{ 
                        fontSize: 12,
                        color: '#1f2937',
                        fontWeight: 500,
                        marginBottom: 4
                      }}>
                        {q.header || q.question || `问题 ${i + 1}`}
                      </div>
                      {q.multiple !== undefined && (
                        <span style={{ 
                          fontSize: 11,
                          color: '#6b7280',
                          padding: '2px 6px',
                          background: '#f3f4f6',
                          borderRadius: 3
                        }}>
                          {q.multiple ? '多选' : '单选'}
                        </span>
                      )}
                      {q.options && q.options.length > 0 && (
                        <div style={{ 
                          fontSize: 11,
                          color: '#6b7280',
                          marginTop: 4,
                          lineHeight: 1.5
                        }}>
                          选项：{q.options.map(opt => opt.label).join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <pre style={{ 
                  fontSize: 11,
                  color: '#374151',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  margin: 0,
                  fontFamily: 'monospace',
                  background: '#ffffff',
                  padding: 8,
                  borderRadius: 4,
                  border: '1px solid #e5e7eb',
                  maxHeight: 300,
                  overflow: 'auto'
                }}>
                  {JSON.stringify(inputData, null, 2)}
                </pre>
              )}
            </div>
          )}
          
          {/* 输出区域 */}
          {tool.output && (
            <div style={{ 
              padding: '10px 12px',
              background: '#f9fafb',
              borderRadius: 6,
              border: '1px solid #e5e7eb'
            }}>
              <div style={{ 
                fontSize: 11, 
                color: '#9ca3af', 
                marginBottom: 8,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                执行结果
              </div>
              <div style={{ 
                fontSize: 11,
                color: '#374151',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: 400,
                overflow: 'auto',
                fontFamily: 'monospace',
                background: '#ffffff',
                padding: 8,
                borderRadius: 4,
                border: '1px solid #e5e7eb'
              }}>
                {tool.output}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ToolCall;
