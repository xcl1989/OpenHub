import React from 'react';
import { Tag, Progress } from 'antd';
import {
  CheckCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';

const TodoListView = ({ todos }) => {
  if (!todos || !Array.isArray(todos) || todos.length === 0) {
    return (
      <div style={{
        padding: '12px 14px',
        background: '#f9fafb',
        borderRadius: 6,
        border: '1px solid #e5e7eb',
        textAlign: 'center'
      }}>
        <span style={{ fontSize: 12, color: '#9ca3af' }}>暂无任务</span>
      </div>
    );
  }

  const completedCount = todos.filter(t => t.status === 'completed').length;
  const total = todos.length;
  const progressPercent = total > 0 ? Math.round((completedCount / total) * 100) : 0;

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#059669', fontSize: 14 }} />;
      case 'in_progress':
        return <LoadingOutlined style={{ color: '#2563eb', fontSize: 14 }} />;
      case 'pending':
      default:
        return <ClockCircleOutlined style={{ color: '#9ca3af', fontSize: 14 }} />;
    }
  };

  const getStatusBg = (status) => {
    switch (status) {
      case 'completed':
        return '#f0fdf4';
      case 'in_progress':
        return '#eff6ff';
      case 'pending':
      default:
        return '#f9fafb';
    }
  };

  const getStatusBorder = (status) => {
    switch (status) {
      case 'completed':
        return '#bbf7d0';
      case 'in_progress':
        return '#bfdbfe';
      case 'pending':
      default:
        return '#e5e7eb';
    }
  };

  const getPriorityTag = (priority) => {
    const config = {
      high: { color: 'red', label: '高', bg: '#fef2f2', border: '#fecaca' },
      medium: { color: 'orange', label: '中', bg: '#fffbeb', border: '#fde68a' },
      low: { color: 'blue', label: '低', bg: '#eff6ff', border: '#bfdbfe' },
    };
    const c = config[priority] || config.low;
    return (
      <Tag
        style={{
          color: c.color,
          background: c.bg,
          border: `1px solid ${c.border}`,
          fontSize: 10,
          borderRadius: 4,
          padding: '1px 6px',
          marginRight: 0
        }}
      >
        {c.label}
      </Tag>
    );
  };

  return (
    <div style={{
      padding: '12px 14px',
      background: '#ffffff',
      borderTop: '1px solid #e5e7eb'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
        gap: 12
      }}>
        <div style={{
          fontSize: 11,
          color: '#6b7280',
          fontWeight: 600,
          letterSpacing: '0.3px'
        }}>
          进度
        </div>
        <div style={{
          flex: 1,
          maxWidth: 200
        }}>
          <Progress
            percent={progressPercent}
            size="small"
            showInfo={false}
            strokeColor="#059669"
            trailColor="#e5e7eb"
          />
        </div>
        <div style={{
          fontSize: 12,
          color: '#374151',
          fontWeight: 600,
          minWidth: 60,
          textAlign: 'right'
        }}>
          {completedCount}/{total} ({progressPercent}%)
        </div>
      </div>

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6
      }}>
        {todos.map((todo, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              background: getStatusBg(todo.status),
              border: `1px solid ${getStatusBorder(todo.status)}`,
              borderRadius: 6,
              transition: 'all 0.2s'
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 18,
              height: 18,
              flexShrink: 0
            }}>
              {getStatusIcon(todo.status)}
            </div>

            <div style={{
              flex: 1,
              fontSize: 12,
              color: '#1f2937',
              lineHeight: 1.5,
              wordBreak: 'break-word'
            }}>
              {todo.content}
            </div>

            {todo.priority && (
              getPriorityTag(todo.priority)
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default TodoListView;
