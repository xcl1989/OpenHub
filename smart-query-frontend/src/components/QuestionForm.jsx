import React from 'react';
import { Form, Input, Radio, Button, Space } from 'antd';

const QuestionForm = ({ questions, onSubmit, onCancel }) => {
  const [form] = Form.useForm();
  
  const handleSubmit = (values) => {
    onSubmit(values);
  };
  
  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSubmit}
      style={{ maxWidth: 600 }}
    >
      {questions.map((q, index) => (
        <Form.Item
          key={index}
          label={
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              {q.header || `问题 ${index + 1}`}
            </div>
          }
          name={q.header || `question_${index}`}
          rules={[{ required: true, message: '请填写此项' }]}
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
                <Input 
                  placeholder={`请输入${q.header || `问题 ${index + 1}`}`}
                  size="large"
                />
              );
            } else {
              return (
                <Radio.Group>
                  {q.options.map((opt, optIndex) => (
                    <Radio 
                      key={optIndex} 
                      value={opt.label}
                      style={{ 
                        display: 'flex',
                        marginBottom: 4,
                        height: 'auto',
                        lineHeight: 1.5
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 500 }}>{opt.label}</div>
                        {opt.description && (
                          <div style={{ fontSize: 11, color: '#6b7280' }}>
                            {opt.description}
                          </div>
                        )}
                      </div>
                    </Radio>
                  ))}
                </Radio.Group>
              );
            }
          })() : (
            <Input 
              placeholder={`请输入${q.header || `问题 ${index + 1}`}`}
              size="large"
            />
          )}
        </Form.Item>
      ))}
      <Form.Item style={{ marginTop: 24 }}>
        <Space>
          <Button type="primary" htmlType="submit" size="large">
            提交
          </Button>
          <Button onClick={onCancel} size="large">
            取消
          </Button>
        </Space>
      </Form.Item>
    </Form>
  );
};

export default QuestionForm;
