import React from 'react';
import {
  Button,
  Spin,
  List,
  Drawer,
  Avatar,
} from 'antd';
import {
  PlusOutlined,
  HistoryOutlined,
  MessageOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import SwipeableListItem from './SwipeableListItem';

const isMobile = () => {
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
};

const HistoryDrawer = ({
  open,
  onClose,
  sessions,
  loading,
  total,
  selectedSessionId,
  onSessionClick,
  onArchiveClick,
  onNewConversation,
  onRefresh,
  onScroll,
  newConversationDisabled,
}) => {
  return (
    <Drawer
      title="历史对话"
      placement="left"
      width={320}
      onClose={onClose}
      open={open}
      styles={{ body: { padding: 0 } }}
    >
      <div style={{ padding: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          block
          size="large"
          onClick={onNewConversation}
          disabled={newConversationDisabled}
          style={{ marginBottom: 16 }}
        >
          新建对话
        </Button>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: '#6b7280' }}>
            共 {total} 条历史记录
          </div>
          <Button
            type="text"
            size="small"
            icon={<HistoryOutlined />}
            onClick={onRefresh}
            loading={loading}
            disabled={loading}
          >
            刷新
          </Button>
        </div>
        <div 
style={{ maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}
onScroll={onScroll}
>
          {loading && sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin tip="加载中..." />
            </div>
          ) : sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>
              <HistoryOutlined style={{ fontSize: 48, marginBottom: 16, display: 'block' }} />
              <div>暂无历史记录</div>
            </div>
          ) : (
          <div>
            {sessions.map((session) => {
              const sessionId = session.session_id || session.id;
              const title = session.title || '无标题';
              let updatedAt = '未知时间';
              if (session.updated_at) {
                if (typeof session.updated_at === 'number') {
                  updatedAt = new Date(session.updated_at).toLocaleString('zh-CN');
                } else if (typeof session.updated_at === 'string') {
                  updatedAt = new Date(session.updated_at).toLocaleString('zh-CN');
                }
              }
              if (session.time?.updated) {
                updatedAt = new Date(session.time.updated).toLocaleString('zh-CN');
              }
              
              const isSelected = selectedSessionId === sessionId;
              
              if (isMobile()) {
                return (
                  <SwipeableListItem
                    key={sessionId}
                    sessionId={sessionId}
                    isSelected={isSelected}
                    onClick={() => sessionId && onSessionClick(sessionId)}
                    onArchive={() => onArchiveClick(sessionId)}
                  >
                    <List.Item.Meta
                      avatar={
                        <Avatar 
                          style={{ background: isSelected ? '#1890ff' : '#1677ff' }}
                          icon={<MessageOutlined />}
                        />
                      }
                      title={
                        <div style={{ 
                          fontSize: 13, 
                          fontWeight: 500,
                          color: isSelected ? '#1890ff' : '#1f2937',
                          maxWidth: 200,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {title}
                        </div>
                      }
                      description={
                        <div style={{ fontSize: 11, color: '#6b7280' }}>
                          <div>{updatedAt}</div>
                          <div style={{ fontSize: 11, color: '#9ca3af' }}>
                            ID: {(sessionId || '').slice(-8)}
                          </div>
                        </div>
                      }
                    />
                  </SwipeableListItem>
                );
              }
              
              return (
                <div key={sessionId} style={{ position: 'relative', overflow: 'hidden', marginBottom: 4, borderRadius: 8 }}>
                  <div
                    className="archive-btn"
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: 0,
                      bottom: 0,
                      width: 80,
                      background: '#ff4d4f',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      opacity: 0,
                      transition: 'opacity 0.2s'
                    }}
                  >
                    <Button
                      type="text"
                      icon={<InboxOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        onArchiveClick(sessionId);
                      }}
                      style={{ color: '#fff', fontSize: 20, padding: 0 }}
                      title="归档会话"
                    />
                  </div>
                  
                  <div
                    onClick={() => sessionId && onSessionClick(sessionId)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 8,
                      cursor: sessionId ? 'pointer' : 'not-allowed',
                      background: isSelected ? '#e6f7ff' : '#fff',
                      border: isSelected ? '1px solid #1890ff' : '1px solid #e5e7eb',
                      transition: 'all 0.2s',
                      opacity: sessionId ? 1 : 0.6
                    }}
                    onMouseEnter={(e) => {
                      if (sessionId) {
                        e.currentTarget.style.borderColor = '#1890ff';
                        e.currentTarget.style.background = isSelected ? '#e6f7ff' : '#f0faff';
                        const btn = e.currentTarget.parentElement?.querySelector('.archive-btn');
                        if (btn) btn.style.opacity = '1';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (sessionId) {
                        e.currentTarget.style.borderColor = isSelected ? '#1890ff' : '#e5e7eb';
                        e.currentTarget.style.background = isSelected ? '#e6f7ff' : '#fff';
                        const btn = e.currentTarget.parentElement?.querySelector('.archive-btn');
                        if (btn) btn.style.opacity = '0';
                      }
                    }}
                  >
                    <List.Item.Meta
                      avatar={
                        <Avatar 
                          style={{ background: isSelected ? '#1890ff' : '#1677ff' }}
                          icon={<MessageOutlined />}
                        />
                      }
                      title={
                        <div style={{ 
                          fontSize: 13, 
                          fontWeight: 500,
                          color: isSelected ? '#1890ff' : '#1f2937',
                          maxWidth: 200,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {title}
                        </div>
                      }
                      description={
                        <div style={{ fontSize: 11, color: '#6b7280' }}>
                          <div>{updatedAt}</div>
                          <div style={{ fontSize: 11, color: '#9ca3af' }}>
                            ID: {(sessionId || '').slice(-8)}
                          </div>
                        </div>
                      }
                    />
                  </div>
                </div>
              );
            })}
          </div>
          )}
        </div>
      </div>
    </Drawer>
  );
};

export default HistoryDrawer;
