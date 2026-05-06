import React, { useEffect, useState, useCallback } from 'react';
import { notification, Button, Tag, Space, Typography } from 'antd';
import { BulbOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { learningService } from '../services/api';

const { Text } = Typography;

let _eventSource = null;

export function startLearningNotificationListener() {
  const token = localStorage.getItem('auth_token');
  if (!token) return;

  if (_eventSource) {
    _eventSource.close();
  }

  const base = import.meta.env.VITE_API_BASE_URL || '/api';
  const url = `${base}/notifications/stream?token=${token}`;

  _eventSource = new EventSource(url);

  _eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'skill_created') {
        showSkillCreatedNotification(data);
      }
    } catch (e) {
      // ignore
    }
  };

  _eventSource.onerror = () => {
    // will auto-reconnect
  };
}

export function stopLearningNotificationListener() {
  if (_eventSource) {
    _eventSource.close();
    _eventSource = null;
  }
}

function showSkillCreatedNotification(data) {
  const key = `skill-${data.pattern_id}`;

  const handleAccept = async () => {
    try {
      await learningService.updatePattern(data.pattern_id, 'accepted');
      notification.success({ message: '已接受', description: `Skill "${data.skill_name}" 已启用`, key, duration: 2 });
    } catch (e) {
      notification.error({ message: '操作失败', key, duration: 2 });
    }
  };

  const handleReject = async () => {
    try {
      await learningService.updatePattern(data.pattern_id, 'rejected');
      notification.info({ message: '已忽略', key, duration: 2 });
    } catch (e) {
      notification.error({ message: '操作失败', key, duration: 2 });
    }
  };

  notification.open({
    key,
    message: (
      <Space>
        <BulbOutlined style={{ color: '#faad14' }} />
        <span>AI 自动学习了新技能</span>
        <Tag color="blue">{data.skill_name}</Tag>
        <Text type="secondary">置信度 {(data.confidence * 100).toFixed(0)}%</Text>
      </Space>
    ),
    description: (
      <div>
        <Text>{data.reasoning || data.description}</Text>
        <div style={{ marginTop: 8 }}>
          <Space>
            <Button size="small" type="primary" icon={<CheckOutlined />} onClick={handleAccept}>
              接受
            </Button>
            <Button size="small" icon={<CloseOutlined />} onClick={handleReject}>
              忽略
            </Button>
          </Space>
        </div>
      </div>
    ),
    duration: 30,
    placement: 'bottomRight',
  });
}

export default function SkillLearningToast() {
  const [patterns, setPatterns] = useState([]);

  const loadPending = useCallback(async () => {
    try {
      const res = await learningService.getPatterns('pending', 1, 5);
      if (res.success) {
        setPatterns(res.data || []);
      }
    } catch (e) {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadPending();
    startLearningNotificationListener();
    return () => stopLearningNotificationListener();
  }, [loadPending]);

  return null;
}
