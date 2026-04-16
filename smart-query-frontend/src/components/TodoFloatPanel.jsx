import React from 'react';
import {
  CheckOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  CloseOutlined,
  FileTextOutlined
} from '@ant-design/icons';

const TodoFloatPanel = ({ todos, visible, onClose }) => {
  if (!visible) return null;

  if (!todos || todos.length === 0) {
    return null;
  }

  const completedCount = todos.filter(t => t.status === 'completed').length;
  const total = todos.length;
  const progressPercent = total > 0 ? Math.round((completedCount / total) * 100) : 0;

  return (
    <div
      style={{
        position: 'absolute',
        top: 'auto',
        bottom: 0,
        right: 0,
        width: 300,
        maxHeight: 320,
        background: '#ffffff',
        borderLeft: '1px solid #e5e7eb',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.08)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 50,
        animation: 'slideInRight 0.2s ease-out',
      }}
    >
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        background: '#fafbfc',
        flexShrink: 0,
      }}>
        <FileTextOutlined style={{ color: '#1890ff', fontSize: 16 }} />
        <span style={{
          flex: 1,
          fontWeight: 600,
          fontSize: 14,
          color: '#1f2937'
        }}>
          任务进度
        </span>
        <span style={{
          fontSize: 12,
          color: '#6b7280',
          background: '#f3f4f6',
          padding: '2px 8px',
          borderRadius: 10,
        }}>
          {completedCount}/{total}
        </span>
        <button
          onClick={onClose}
          style={{
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            padding: '4px',
            color: '#9ca3af',
            fontSize: 14,
            lineHeight: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 4,
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#f3f4f6'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
        >
          <CloseOutlined style={{ fontSize: 12 }} />
        </button>
      </div>

      <div style={{
        padding: '12px 16px 8px',
        borderBottom: '1px solid #f0f0f0',
        flexShrink: 0,
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <div style={{
            flex: 1,
            height: 6,
            background: '#e5e7eb',
            borderRadius: 3,
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${progressPercent}%`,
              height: '100%',
              background: progressPercent === 100 ? '#059669' : '#1890ff',
              borderRadius: 3,
              transition: 'width 0.3s ease',
            }} />
          </div>
          <span style={{
            fontSize: 11,
            color: progressPercent === 100 ? '#059669' : '#6b7280',
            fontWeight: 600,
            minWidth: 36,
          }}>
            {progressPercent}%
          </span>
        </div>
      </div>

      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '10px 12px',
      }}>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6
        }}>
          {todos.map((todo, index) => {
            const getStatusIcon = () => {
              switch (todo.status) {
                case 'completed':
                  return <CheckOutlined style={{ color: '#059669', fontSize: 12 }} />;
                case 'in_progress':
                  return <LoadingOutlined style={{ color: '#2563eb', fontSize: 12 }} />;
                case 'pending':
                default:
                  return <ClockCircleOutlined style={{ color: '#d1d5db', fontSize: 12 }} />;
              }
            };

            const getPriorityConfig = () => {
              switch (todo.priority) {
                case 'high':
                  return { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: '高' };
                case 'medium':
                  return { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: '中' };
                case 'low':
                  return { color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe', label: '低' };
                default:
                  return null;
              }
            };

            const priorityConfig = getPriorityConfig();

            return (
              <div
                key={index}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  padding: '8px 10px',
                  background: todo.status === 'completed' ? '#f9fafb' :
                              todo.status === 'in_progress' ? '#f0f9ff' : '#ffffff',
                  border: `1px solid ${todo.status === 'completed' ? '#e5e7eb' :
                                          todo.status === 'in_progress' ? '#bfdbfe' : '#f3f4f6'}`,
                  borderRadius: 6,
                  opacity: todo.status === 'completed' ? 0.7 : 1,
                }}
              >
                <div style={{ flexShrink: 0, marginTop: 2 }}>
                  {getStatusIcon()}
                </div>
                <div style={{
                  flex: 1,
                  fontSize: 12,
                  color: todo.status === 'completed' ? '#9ca3af' : '#374151',
                  lineHeight: 1.5,
                  wordBreak: 'break-word',
                }}>
                  {todo.content}
                </div>
                {priorityConfig && (
                  <span style={{
                    fontSize: 10,
                    color: priorityConfig.color,
                    background: priorityConfig.bg,
                    border: `1px solid ${priorityConfig.border}`,
                    borderRadius: 4,
                    padding: '1px 5px',
                    flexShrink: 0,
                  }}>
                    {priorityConfig.label}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
};

export default TodoFloatPanel;
