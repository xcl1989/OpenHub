import React, { useState, useMemo, useRef, useCallback } from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer } from 'recharts';
import { Button, Select, Space, Tooltip, Radio, Popover } from 'antd';
import { BarChartOutlined, LineChartOutlined, PieChartOutlined, TableOutlined, SettingOutlined, CloseOutlined } from '@ant-design/icons';
import './TableWithChart.css';

const { Option } = Select;

// 图表颜色
const CHART_COLORS = [
  '#1890ff', '#28a745', '#ffc107', '#dc3545', '#6f42c1',
  '#00bcd4', '#ff5722', '#795548', '#607d8b', '#e91e63'
];

const TableWithChart = ({ headers, rows }) => {
  const [showChart, setShowChart] = useState(false);
  const [chartType, setChartType] = useState('bar');
  const [hovered, setHovered] = useState(false);
  const [configVisible, setConfigVisible] = useState(false);
  const chartContainerRef = useRef(null);

  // 计算默认字段
  const { defaultDimensionField, defaultMetricFields } = useMemo(() => {
    if (!headers || headers.length === 0 || !rows || rows.length === 0) {
      return { defaultDimensionField: null, defaultMetricFields: [] };
    }
    
    const dimField = headers[0];
    const numericFields = headers.filter(h => {
      const sampleValue = rows[0]?.[h];
      return typeof sampleValue === 'number';
    });
    const metFields = numericFields.length > 0 ? [numericFields[0]] : [headers.filter(h => h !== dimField)[0] || dimField];
    
    return { defaultDimensionField: dimField, defaultMetricFields: metFields };
  }, [headers, rows]);

  // 使用 useMemo 的结果作为初始值
  const [dimensionField, setDimensionField] = useState(defaultDimensionField);
  const [metricFields, setMetricFields] = useState(defaultMetricFields);

  // 准备图表数据（合并相同维度值）
  const chartData = useMemo(() => {
    const fieldsToUse = chartType === 'pie' && metricFields.length > 1 ? [metricFields[0]] : metricFields;
    if (!dimensionField || fieldsToUse.length === 0) return [];
    
    // 饼图模式下，使用维度字段分类，指标字段作为数值
    if (chartType === 'pie') {
      const pieField = fieldsToUse[0];
      if (!pieField) return [];
      
      const parsedRows = rows.map(row => {
        const dimValue = String(row[dimensionField] || '');
        let rawValue = row[pieField];
        
        if (rawValue === undefined || rawValue === null || rawValue === '') {
          const matchingKey = Object.keys(row).find(key => 
            key.toLowerCase().includes(pieField.toLowerCase()) ||
            key.includes('金额') || 
            key.includes('收款') ||
            key.includes('价格') ||
            key.includes('费用')
          );
          if (matchingKey) {
            rawValue = row[matchingKey];
          }
        }
        
        let numValue = 0;
        let isValid = false;
        
        if (typeof rawValue === 'number') {
          numValue = rawValue;
          isValid = true;
        } else if (typeof rawValue === 'string') {
          const cleaned = rawValue.replace(/[,，\s¥元]/g, '');
          const parsed = parseFloat(cleaned);
          if (!isNaN(parsed) && cleaned !== '') {
            numValue = parsed;
            isValid = true;
          }
        }
        
        return { dimValue, numValue, isValid };
      });
      
      const validCount = parsedRows.filter(r => r.isValid).length;
      const totalRows = parsedRows.length;
      const validRatio = totalRows > 0 ? validCount / totalRows : 0;
      
      const dataMap = new Map();
      
      parsedRows.forEach(({ dimValue, numValue, isValid }) => {
        if (!dimValue) return;
        if (validRatio > 0.5 && !isValid) return;
        if (validRatio > 0.5 && numValue === 0) return;
        
        if (!dataMap.has(dimValue)) {
          dataMap.set(dimValue, { name: dimValue, value: 0 });
        }
        
        const dataPoint = dataMap.get(dimValue);
        dataPoint.value += validRatio > 0.5 ? numValue : 1;
      });
      
      return Array.from(dataMap.values()).filter(item => item.value > 0);
    }
    
    // 柱状图/折线图模式
    const dataMap = new Map();
    
    rows.forEach(row => {
      const dimValue = String(row[dimensionField] || '');
      
      if (!dataMap.has(dimValue)) {
        dataMap.set(dimValue, {
          name: dimValue,
          count: 0,
          ...Object.fromEntries(fieldsToUse.map(f => [f, 0]))
        });
      }
      
      const dataPoint = dataMap.get(dimValue);
      
      fieldsToUse.forEach(field => {
        const rawValue = row[field];
        let numValue = 0;
        if (typeof rawValue === 'number') {
          numValue = rawValue;
        } else if (typeof rawValue === 'string') {
          const cleaned = rawValue.replace(/[,，\s¥元]/g, '');
          const parsed = parseFloat(cleaned);
          numValue = isNaN(parsed) ? 0 : parsed;
        }
        dataPoint[field] += numValue;
      });
    });
    
    return Array.from(dataMap.values());
  }, [rows, dimensionField, metricFields, chartType]);

  // 渲染图表
  const renderChart = useCallback(() => {
    if (chartData.length === 0) {
      return <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>暂无数据</div>;
    }

    const displayMetrics = chartType === 'pie' && metricFields.length > 1 ? [metricFields[0]] : metricFields;

    if (chartType === 'bar') {
      return (
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis width={80} />
            <RechartsTooltip />
            <Legend />
            {displayMetrics.map((field, index) => (
              <Bar 
                key={field} 
                dataKey={field} 
                name={field}
                fill={CHART_COLORS[index % CHART_COLORS.length]} 
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      );
    }

    if (chartType === 'line') {
      return (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis width={80} />
            <RechartsTooltip />
            <Legend />
            {displayMetrics.map((field, index) => (
              <Line 
                key={field} 
                type="monotone" 
                dataKey={field} 
                name={field}
                stroke={CHART_COLORS[index % CHART_COLORS.length]} 
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      );
    }

    if (chartType === 'pie') {
      const pieField = displayMetrics[0];
      if (!pieField || chartData.length === 0) return null;
      
      const total = chartData.reduce((sum, item) => sum + (item.value || 0), 0);
      
      if (total === 0) {
        return <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>数据无效，无法显示饼图</div>;
      }
      
      const renderLabel = ({ name, value, startAngle, endAngle }) => {
        const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
        const angle = endAngle - startAngle;
        if (angle < 18) return null;
        const displayName = name.length > 10 ? name.substring(0, 8) + '...' : name;
        return `${displayName}: ${percentage}%`;
      };
      
      return (
        <ResponsiveContainer width="100%" height={400}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              labelLine={(entry) => {
                const angle = entry.endAngle - entry.startAngle;
                return angle >= 18;
              }}
              label={renderLabel}
              outerRadius={120}
              innerRadius={40}
              paddingAngle={2}
              fill="#8884d8"
              dataKey="value"
              name={pieField}
              stroke="#fff"
              strokeWidth={2}
            >
              {chartData.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={CHART_COLORS[index % CHART_COLORS.length]}
                  style={{ cursor: 'pointer' }}
                />
              ))}
            </Pie>
            <RechartsTooltip 
              formatter={(value) => [`${value.toLocaleString()} 元`, pieField]}
              contentStyle={{
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '12px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
              }}
            />
            <Legend 
              verticalAlign="bottom" 
              height={36}
              formatter={(value, entry, index) => {
                const item = chartData[index];
                const percentage = item && total > 0 ? ((item.value / total) * 100).toFixed(1) : 0;
                return `${value} (${percentage}%)`;
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      );
    }

    return null;
  }, [chartData, chartType, metricFields]);

  // 渲染表格
  const renderTable = useCallback(() => (
    <div style={{ overflow: 'auto', margin: '12px 0' }}>
      <table
        style={{
          borderCollapse: 'collapse',
          width: '100%',
          fontSize: '14px'
        }}
      >
        <thead>
          <tr>
            {headers.map((header, index) => (
              <th
                key={index}
                style={{
                  border: '1px solid #d9d9d9',
                  padding: '8px 12px',
                  background: '#fafafa',
                  fontWeight: 600,
                  textAlign: 'left'
                }}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {headers.map((header, colIndex) => (
                <td
                  key={colIndex}
                  style={{
                    border: '1px solid #d9d9d9',
                    padding: '8px 12px'
                  }}
                >
                  {row[header]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ), [headers, rows]);

  // 配置面板内容
  const ConfigPanelContent = useCallback(() => (
    <div style={{ width: 300 }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: 12,
        paddingBottom: 8,
        borderBottom: '1px solid #e5e7eb'
      }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>图表配置</span>
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={() => setConfigVisible(false)}
        />
      </div>

      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>图表类型</div>
          <Radio.Group
            value={chartType}
            onChange={(e) => setChartType(e.target.value)}
            style={{ width: '100%' }}
            size="small"
          >
            <Space size="small" wrap>
              <Radio.Button value="bar"><BarChartOutlined /> 柱状图</Radio.Button>
              <Radio.Button value="line"><LineChartOutlined /> 折线图</Radio.Button>
              <Radio.Button value="pie"><PieChartOutlined /> 饼图</Radio.Button>
            </Space>
          </Radio.Group>
        </div>

        <div>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>
            {chartType === 'pie' ? '分类字段' : '维度字段（X 轴）'}
          </div>
          <Select
            value={dimensionField}
            onChange={setDimensionField}
            style={{ width: '100%' }}
            size="small"
            popupMatchSelectWidth={300}
          >
            {headers.map(header => (
              <Option key={header} value={header}>{header}</Option>
            ))}
          </Select>
        </div>

        <div>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>
            指标字段{chartType !== 'pie' && '（Y 轴）'}
          </div>
          <Select
            mode={chartType === 'pie' ? undefined : 'multiple'}
            value={chartType === 'pie' && metricFields.length > 1 ? [metricFields[0]] : metricFields}
            onChange={setMetricFields}
            style={{ width: '100%' }}
            size="small"
            maxTagCount="responsive"
            placeholder="请选择字段"
            popupMatchSelectWidth={300}
          >
            {headers.map(header => (
              <Option key={header} value={header}>
                {header}
              </Option>
            ))}
          </Select>
        </div>

        <Space style={{ width: '100%', marginTop: 8 }} size="small">
          <Button
            type="primary"
            size="small"
            style={{ flex: 1 }}
            onClick={() => {
              setShowChart(true);
              setConfigVisible(false);
            }}
          >
            应用并查看图表
          </Button>
        </Space>
      </Space>
    </div>
  ), [chartType, dimensionField, metricFields, headers]);

  return (
    <div
      className="table-with-chart-container"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {hovered && rows && rows.length > 0 && (
        <div className="chart-toolbar">
          {!showChart ? (
            <Popover
              content={<ConfigPanelContent />}
              open={configVisible}
              onOpenChange={setConfigVisible}
              trigger="click"
              placement="rightTop"
              overlayClassName="chart-config-popover"
              overlayStyle={{ maxWidth: 320 }}
            >
              <Tooltip title="查看图表">
                <Button
                  type="primary"
                  icon={<SettingOutlined />}
                  size="small"
                >
                  图表
                </Button>
              </Tooltip>
            </Popover>
          ) : (
            <>
              <Tooltip title="切换回表格">
                <Button
                  icon={<TableOutlined />}
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowChart(false);
                  }}
                >
                  表格
                </Button>
              </Tooltip>
              <Popover
                content={<ConfigPanelContent />}
                open={configVisible}
                onOpenChange={setConfigVisible}
                trigger="click"
                placement="rightTop"
                overlayClassName="chart-config-popover"
                overlayStyle={{ maxWidth: 320 }}
              >
                <Tooltip title="配置图表">
                  <Button
                    icon={<SettingOutlined />}
                    size="small"
                  >
                    配置
                  </Button>
                </Tooltip>
              </Popover>
            </>
          )}
        </div>
      )}

      {showChart ? (
        <div ref={chartContainerRef} className="chart-content">
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>
              {chartType === 'bar' && <BarChartOutlined style={{ marginRight: 8, color: '#1890ff' }} />}
              {chartType === 'line' && <LineChartOutlined style={{ marginRight: 8, color: '#28a745' }} />}
              {chartType === 'pie' && <PieChartOutlined style={{ marginRight: 8, color: '#ffc107' }} />}
              {dimensionField && Array.isArray(metricFields) && metricFields.length > 0 && (
                <span>{dimensionField} - {metricFields.join(', ')}</span>
              )}
            </div>
          </div>
          <div className="chart-content-animated">
            {renderChart()}
          </div>
        </div>
      ) : (
        renderTable()
      )}
    </div>
  );
};

export default React.memo(TableWithChart, (prevProps, nextProps) => {
  return prevProps.headers === nextProps.headers && prevProps.rows === nextProps.rows;
});
