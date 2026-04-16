import { useState, useEffect, useRef, useCallback } from 'react';
import { Badge, Popover, List, Typography, Space, Tag, Tabs } from 'antd';
import { BellOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { notificationService } from '../services/api';

const { Text } = Typography;

const getSSEUrl = () => {
  const apiBase = import.meta.env.VITE_API_BASE_URL || '/api';
  const origin = window.location.origin;
  return `${origin}${apiBase}/notifications/stream`;
};

function NotificationBell() {
  const [notifications, setNotifications] = useState([]);
  const [readNotifications, setReadNotifications] = useState([]);
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('unread');
  const esRef = useRef(null);
  const reconnectDelayRef = useRef(5000);
  const reconnectTimerRef = useRef(null);

  const fetchUnread = useCallback(async () => {
    try {
      const res = await notificationService.getUnread();
      if (res.ok) {
        setNotifications(res.notifications || []);
      }
    } catch {}
  }, []);

  const fetchRead = useCallback(async () => {
    try {
      const res = await notificationService.getAll();
      if (res.ok) {
        setReadNotifications((res.notifications || []).filter(n => n.is_read));
      }
    } catch {}
  }, []);

  const connectSSE = useCallback(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) return;

    const es = new EventSource(`${getSSEUrl()}?token=${encodeURIComponent(token)}`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'notification') {
          setNotifications((prev) => [data.data, ...prev]);
        } else if (data.type === 'unread_count') {
          fetchUnread();
        }
      } catch {}
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(delay * 2, 30000);
      reconnectTimerRef.current = setTimeout(connectSSE, delay);
    };
  }, [fetchUnread]);

  useEffect(() => {
    fetchUnread();
    connectSSE();

    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [connectSSE, fetchUnread]);

  const handleMarkRead = async (id) => {
    try {
      await notificationService.markRead(id);
      const notif = notifications.find(n => n.id === id);
      if (notif) {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
        setReadNotifications((prev) => [{ ...notif, is_read: 1 }, ...prev]);
      }
    } catch {}
  };

  const unreadCount = notifications.length;

  const tabContentStyle = { maxHeight: 360, overflowY: 'auto' };

  const renderNotificationList = (list) => (
    <div style={tabContentStyle}>
      {list.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          暂无消息
        </div>
      ) : (
        <List
          size="small"
          dataSource={list}
          renderItem={(item) => (
            <List.Item
              style={{ cursor: 'pointer', padding: '8px 12px' }}
              onClick={() => !item.is_read && handleMarkRead(item.id)}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <ClockCircleOutlined style={{ color: '#1890ff' }} />
                    <Text strong style={{ fontSize: 13 }}>
                      {item.task_name || '定时任务'}
                    </Text>
                    {!item.is_read && <Tag color="blue" style={{ fontSize: 10 }}>未读</Tag>}
                  </Space>
                }
                description={
                  <div>
                    <Text
                      type="secondary"
                      style={{ fontSize: 12 }}
                      ellipsis={{ rows: 2 }}
                    >
                      {item.result_preview || '执行完成'}
                    </Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {item.created_at}
                    </Text>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      )}
    </div>
  );

  const content = (
    <div style={{ width: 380 }}>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        onTabClick={(key) => {
          if (key === 'read') fetchRead();
        }}
        items={[
          {
            key: 'unread',
            label: `未读消息${unreadCount > 0 ? ` (${unreadCount})` : ''}`,
            children: renderNotificationList(notifications),
          },
          {
            key: 'read',
            label: '已读消息',
            children: renderNotificationList(readNotifications),
          },
        ]}
      />
    </div>
  );

  return (
    <Popover
      content={content}
      title={
        <Space>
          <BellOutlined />
          <span>定时任务通知</span>
        </Space>
      }
      trigger="click"
      open={open}
      onOpenChange={setOpen}
      placement="bottomRight"
    >
      <Badge count={unreadCount} size="small" offset={[-2, 2]}>
        <BellOutlined style={{ fontSize: 16, cursor: 'pointer' }} />
      </Badge>
    </Popover>
  );
}

export default NotificationBell;
