import { useState, useEffect, useRef, useCallback } from 'react';
import { Badge, Popover, Drawer, Typography, Tabs } from 'antd';
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
  const [isMobile, setIsMobile] = useState(false);
  const esRef = useRef(null);
  const reconnectDelayRef = useRef(5000);
  const reconnectTimerRef = useRef(null);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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

  const tabContentStyle = isMobile
    ? { maxHeight: 'calc(100vh - 120px)', overflowY: 'auto' }
    : { maxHeight: 360, overflowY: 'auto' };

  const formatTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}天前`;
    const pad = (n) => String(n).padStart(2, '0');
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const renderNotificationList = (list) => (
    <div style={tabContentStyle}>
      {list.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          暂无消息
        </div>
      ) : (
        <div>
          {list.map((item) => (
            <div
              key={item.id}
              style={{
                cursor: 'pointer',
                padding: isMobile ? '12px 16px' : '10px 14px',
                borderBottom: '1px solid #f0f0f0',
                display: 'flex',
                alignItems: 'flex-start',
                gap: isMobile ? 10 : 8,
              }}
              onClick={() => !item.is_read && handleMarkRead(item.id)}
            >
              <div
                style={{
                  width: isMobile ? 32 : 28,
                  height: isMobile ? 32 : 28,
                  borderRadius: '50%',
                  background: '#e6f4ff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  marginTop: 2,
                }}
              >
                <ClockCircleOutlined style={{ color: '#1890ff', fontSize: isMobile ? 14 : 12 }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    marginBottom: 2,
                  }}
                >
                  <Text
                    strong
                    style={{
                      fontSize: isMobile ? 15 : 13,
                      lineHeight: 1.4,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {item.task_name || '定时任务'}
                  </Text>
                  {!item.is_read && (
                    <span
                      style={{
                        fontSize: 10,
                        lineHeight: '16px',
                        height: 18,
                        padding: '0 6px',
                        borderRadius: 4,
                        background: '#e6f4ff',
                        color: '#1890ff',
                        border: '1px solid #91caff',
                        flexShrink: 0,
                      }}
                    >
                      未读
                    </span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: isMobile ? 13 : 12,
                    color: '#8c8c8c',
                    lineHeight: 1.5,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: isMobile ? 1 : 2,
                    WebkitBoxOrient: 'vertical',
                    wordBreak: 'break-all',
                  }}
                >
                  {item.result_preview || '执行完成'}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: '#bfbfbf',
                    marginTop: 4,
                  }}
                >
                  {formatTime(item.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const tabBar = (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '8px 12px',
        borderBottom: '1px solid #f0f0f0',
      }}
    >
      {[
        { key: 'unread', label: `未读${unreadCount > 0 ? ` ${unreadCount}` : ''}` },
        { key: 'read', label: '已读' },
      ].map((t) => (
        <div
          key={t.key}
          onClick={() => {
            setActiveTab(t.key);
            if (t.key === 'read') fetchRead();
          }}
          style={{
            flex: 1,
            textAlign: 'center',
            padding: '6px 0',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: activeTab === t.key ? 600 : 400,
            color: activeTab === t.key ? '#1677ff' : '#595959',
            background: activeTab === t.key ? '#e6f4ff' : 'transparent',
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
        >
          {t.label}
        </div>
      ))}
    </div>
  );

  const content = isMobile ? (
    <div style={{ width: '100%' }}>
      {tabBar}
      {activeTab === 'unread'
        ? renderNotificationList(notifications)
        : renderNotificationList(readNotifications)}
    </div>
  ) : (
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

  const bell = (
    <Badge count={unreadCount} size="small" offset={[-2, 2]}>
      <BellOutlined
        style={{ fontSize: 16, cursor: 'pointer' }}
        onClick={() => isMobile && setOpen(true)}
      />
    </Badge>
  );

  const titleNode = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <BellOutlined />
      <span>定时任务通知</span>
    </div>
  );

  if (isMobile) {
    return (
      <>
        {bell}
        <Drawer
          title={titleNode}
          placement="right"
          open={open}
          onClose={() => setOpen(false)}
          width="85vw"
          bodyStyle={{ padding: 0 }}
        >
          {content}
        </Drawer>
      </>
    );
  }

  return (
    <Popover
      content={content}
      title={titleNode}
      trigger="click"
      open={open}
      onOpenChange={setOpen}
      placement="bottomRight"
    >
      {bell}
    </Popover>
  );
}

export default NotificationBell;
