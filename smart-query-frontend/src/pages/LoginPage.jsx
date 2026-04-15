import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Typography } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { authService } from '../services/api';
import { useNavigate } from 'react-router-dom';

const { Title } = Typography;

const LoginPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values) => {
    setLoading(true);
    try {
      const result = await authService.login(values.username, values.password);
      if (result.success) {
        message.success('登录成功');
        navigate('/');
      } else {
        message.error(result.message || '登录失败');
      }
    } catch (error) {
      console.error('Login error:', error);
      if (error.response && error.response.status === 401) {
        message.error('用户名或密码错误');
      } else {
        message.error('登录失败，请稍后重试');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100dvh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#f5f7fa',
      padding: '16px',
      boxSizing: 'border-box'
    }}>
      <Card
        style={{
          width: '100%',
          maxWidth: 400,
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}
        styles={{ body: { padding: 0 } }}
      >
        <div style={{ padding: '24px 24px 0' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <Title level={2} style={{ 
              marginBottom: 8, 
              color: '#1f2937',
              fontSize: 'clamp(20px, 5vw, 24px)'
            }}>
              OpenHub 平台
            </Title>
            <Typography.Text type="secondary" style={{ 
              color: '#6b7280',
              fontSize: 'clamp(12px, 3.5vw, 14px)'
            }}>
              用户登录
            </Typography.Text>
          </div>

          <Form
            name="login"
            onFinish={onFinish}
            autoComplete="off"
            size="large"
            style={{ paddingBottom: '24px' }}
          >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
            style={{ marginBottom: 16 }}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
              autoComplete="username"
              size="large"
              style={{ fontSize: 'clamp(14px, 4vw, 16px)' }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
            style={{ marginBottom: 20 }}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              autoComplete="current-password"
              size="large"
              style={{ fontSize: 'clamp(14px, 4vw, 16px)' }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
              style={{
                height: 44,
                background: '#1677ff',
                border: 'none',
                fontSize: 'clamp(14px, 4vw, 16px)',
                fontWeight: 500
              }}
            >
              登录
            </Button>
            </Form.Item>
          </Form>
        </div>
      </Card>
    </div>
  );
};

export default LoginPage;
