import React, { useState } from 'react';
import { Form, Input, Radio, Button, Space } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';

const QuestionFormInline = ({ questions, onSubmit, onCancel }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  
  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      await onSubmit(values);
    } finally {
      setLoading(false);
    }
  };
  
  // 如果问题超过 2 个，默认折叠
  React.useEffect(() => {
    if (questions.length > 2) {
      setCollapsed(true);
    }
  }, [questions.length]);
  
  return (
    <div style={{ 
      background: '#f9fafb', 
      borderRadius: '8px',
      border: '1px solid #e5e7eb',
      overflow: 'hidden'
    }}>
      {collapsed && questions.length > 2 && (
        <div 
          onClick={() => setCollapsed(false)}
          style={{
            padding: '10px 16px',
            background: '#eff6ff',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 13,
            color: '#2563eb'
          }}
        >
          <QuestionCircleOutlined />
          <span>需要填写 {questions.length} 个问题，点击展开</span>
        </div>
      )}
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        size="middle"
        style={{ 
          background: '#ffffff', 
          padding: collapsed ? 0 : '14px',
          borderRadius: '8px',
          opacity: collapsed ? 0.4 : 1,
          pointerEvents: collapsed ? 'none' : 'auto'
        }}
      >
        {questions.map((q, index) => (
          <Form.Item
            key={index}
            label={
              <div style={{ 
                fontWeight: 600, 
                marginBottom: 6, 
                fontSize: 13,
                color: '#1f2937',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 4
              }}>
                <span style={{ 
                  color: '#dc2626',
                  fontSize: 13
                }}>*</span>
                <span>
                  {q.header || `问题 ${index + 1}`}
                  {q.question && (
                    <div style={{ 
                      fontWeight: 400, 
                      fontSize: 11, 
                      color: '#6b7280',
                      marginTop: 3,
                      lineHeight: 1.4
                    }}>
                      {q.question}
                    </div>
                  )}
                </span>
              </div>
            }
            name={q.header || `question_${index}`}
            rules={[{ required: true, message: '请填写此项' }]}
            style={{ marginBottom: index < questions.length - 1 ? 12 : 0 }}
          >
            {q.options && q.options.length > 0 ? (() => {
              const hasTypeOwnAnswer = q.options.some(opt => 
                opt.label === 'Type your own answer' || 
                opt.label.includes('手动输入') ||
                opt.label.includes('自己输入') ||
                opt.label.includes('请输入') ||
                opt.label.toLowerCase().includes('type your') ||
                opt.label.toLowerCase().includes('enter your')
              );
              
              const shouldShowInput = hasTypeOwnAnswer || 
                (q.options.length === 1 && (
                  q.options[0].description?.includes('输入') ||
                  q.options[0].label?.includes('请输入')
                ));
              
              if (shouldShowInput) {
                return (
                  <Input.TextArea
                    placeholder={`请输入${q.header || `问题 ${index + 1}`}`}
                    rows={2}
                    style={{ 
                      resize: 'vertical',
                      borderRadius: 6,
                      borderColor: '#d1d5db',
                      fontSize: 13
                    }}
                    showCount
                    maxLength={200}
                    size="middle"
                  />
                );
              } else {
                return (
                  <Radio.Group style={{ width: '100%' }} size="middle">
                    {q.options.map((opt, optIndex) => (
                      <div
                        key={optIndex}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          marginBottom: optIndex < q.options.length - 1 ? 8 : 0,
                          padding: '9px 11px',
                          border: '1px solid #e5e7eb',
                          borderRadius: 6,
                          transition: 'all 0.2s',
                          cursor: 'pointer',
                          gap: 8
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = '#3b82f6';
                          e.currentTarget.style.background = '#eff6ff';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = '#e5e7eb';
                          e.currentTarget.style.background = '#ffffff';
                        }}
                      >
                        <Radio 
                          value={opt.label}
                          style={{ marginTop: 1 }}
                        >
                          <div style={{ flex: 1, lineHeight: 1.4 }}>
                            <div style={{ fontWeight: 500, fontSize: 13, color: '#1f2937' }}>
                              {opt.label}
                            </div>
                            {opt.description && (
                              <div style={{ fontSize: 11, color: '#6b7280', marginTop: 3, lineHeight: 1.3 }}>
                                {opt.description}
                              </div>
                            )}
                          </div>
                        </Radio>
                      </div>
                    ))}
                  </Radio.Group>
                );
              }
            })() : (
              <Input.TextArea
                placeholder={`请输入${q.header || `问题 ${index + 1}`}`}
                rows={2}
                style={{ 
                  resize: 'vertical',
                  borderRadius: 6,
                  borderColor: '#d1d5db',
                  fontSize: 13
                }}
                showCount
                maxLength={200}
                size="middle"
              />
            )}
          </Form.Item>
        ))}
        {!collapsed && (
          <Form.Item style={{ 
            marginTop: 14, 
            marginBottom: 0,
            paddingTop: 12,
            borderTop: '1px solid #e5e7eb'
          }}>
            <Space size="middle">
              <Button 
                type="primary" 
                htmlType="submit" 
                loading={loading}
                size="middle"
                style={{ 
                  borderRadius: 6,
                  padding: '6px 20px',
                  fontWeight: 500
                }}
              >
                {loading ? '提交中...' : '提交'}
              </Button>
              <Button 
                onClick={onCancel} 
                size="middle"
                disabled={loading}
                style={{ 
                  borderRadius: 6,
                  padding: '6px 20px'
                }}
              >
                取消
              </Button>
            </Space>
          </Form.Item>
        )}
      </Form>
    </div>
  );
};

export default QuestionFormInline;
