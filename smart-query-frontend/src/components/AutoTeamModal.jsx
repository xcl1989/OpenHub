import React, { useState } from 'react';
import { Modal, Input, Steps, Spin, Alert, Tag, Space, Button, Card, Typography, Descriptions, message } from 'antd';
import { TeamOutlined, RobotOutlined, ThunderboltOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { teamService } from '../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

function AutoTeamModal({ visible, onClose, isMobile }) {
  const [requirement, setRequirement] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [execLoading, setExecLoading] = useState(false);
  const [execResult, setExecResult] = useState(null);

  const handleAutoCreate = async () => {
    if (!requirement.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await teamService.autoCreate(requirement.trim());
      if (res.ok) {
        setResult(res);
      } else {
        setError(res.detail || '自动组队失败');
      }
    } catch (err) {
      setError(err?.response?.data?.detail || '网络错误，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setRequirement('');
    setLoading(false);
    setResult(null);
    setError('');
    setExecResult(null);
    setExecLoading(false);
    onClose(result);
  };

  const handleExecute = async () => {
    const desc = requirement.trim();
    if (!desc || desc.length < 5) {
      message.warning('请输入至少5个字符的任务描述');
      return;
    }
    setExecLoading(true);
    setExecResult(null);
    try {
      const res = await teamService.execute(result.team.id, desc);
      if (res.ok) {
        setExecResult(res.result || '执行完成');
        message.success('团队执行完成');
      } else {
        message.error(res.detail || '执行失败');
      }
    } catch (err) {
      message.error(err?.response?.data?.detail || '执行失败');
    } finally {
      setExecLoading(false);
    }
  };

  return (
    <Modal
      title={<Space><ThunderboltOutlined /> 自动组建智能体团队</Space>}
      open={visible}
      onCancel={handleClose}
      width={isMobile ? '95%' : 640}
      footer={null}
      destroyOnClose
    >
      {!result && !loading && (
        <div>
          <Paragraph type="secondary" style={{ marginBottom: 12 }}>
            描述你的需求，系统将自动分析并从可用智能体中匹配合适的成员组建团队。
          </Paragraph>
          <TextArea
            rows={4}
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            placeholder="例如：构建一个全栈 Web 应用，需要前端开发、后端 API、数据库设计和测试"
            maxLength={1000}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {requirement.length} / 1000
            </Text>
            <div>
              <Button onClick={handleClose} style={{ marginRight: 8 }}>取消</Button>
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleAutoCreate}
                disabled={!requirement.trim() || requirement.trim().length < 5}
                loading={loading}
              >
                开始组队
              </Button>
            </div>
          </div>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '30px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Steps
              direction="vertical"
              size="small"
              current={1}
              items={[
                { title: '分析需求', description: '拆解为子任务...' },
                { title: '匹配智能体', description: '从可用智能体中选择最佳成员...' },
                { title: '组建团队', description: '创建团队并分配角色...' },
              ]}
            />
          </div>
          <Text type="secondary" style={{ marginTop: 12, display: 'block' }}>
            预计需要 20-40 秒，请耐心等待...
          </Text>
        </div>
      )}

      {error && (
        <Alert
          type="error"
          message="组队失败"
          description={error}
          showIcon
          style={{ marginBottom: 12 }}
          action={<Button size="small" onClick={handleAutoCreate}>重试</Button>}
        />
      )}

      {result && (
        <div>
          <Alert
            type="success"
            message={<Space><CheckCircleOutlined /> 团队「{result.team?.name}」已创建！</Space>}
            description={result.team?.description}
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Card size="small" title="编排者" style={{ marginBottom: 12 }}>
            <Space>
              <RobotOutlined />
              <Text strong>{result.team?.orchestrator_entity_id}</Text>
              <Tag color="gold">编排协调</Tag>
            </Space>
          </Card>

          <Card size="small" title={<Space><TeamOutlined />任务分配 ({result.assignments?.length || 0})</Space>}>
            {result.assignments?.map((a, i) => (
              <div key={i} style={{
                padding: '8px 0',
                borderBottom: i < result.assignments.length - 1 ? '1px solid #f0f0f0' : 'none',
              }}>
                <div>
                  <Tag color="blue">{a.entity_id}</Tag>
                  <Text strong>{a.subtask}</Text>
                </div>
                <div style={{ marginTop: 4, paddingLeft: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{a.rationale}</Text>
                </div>
              </div>
            ))}
          </Card>

          <div style={{ marginTop: 12, textAlign: 'right' }}>
            <Space>
              <Tag color={result.is_permanent ? 'green' : 'orange'}>
                {result.is_permanent ? '永久团队' : '一次性团队'}
              </Tag>
              {!execResult && (
                <Button icon={<ThunderboltOutlined />} loading={execLoading} onClick={handleExecute}>
                  立即执行
                </Button>
              )}
              <Button type="primary" onClick={handleClose}>完成</Button>
            </Space>
          </div>

          {execResult && (
            <Card size="small" title="执行结果" style={{ marginTop: 12 }}>
              <div style={{ maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6 }}>
                {execResult}
              </div>
            </Card>
          )}
        </div>
      )}
    </Modal>
  );
}

export default AutoTeamModal;
