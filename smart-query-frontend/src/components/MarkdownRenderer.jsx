import React, { useRef, useEffect, useState, useMemo, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import TableWithChart from './TableWithChart';

// 从 HTML 表格元素解析数据
const parseHtmlTable = (tableElement) => {
  const headers = [];
  const rows = [];
  
  if (!tableElement) return { headers: [], rows: [] };
  
  // 获取表头
  const thead = tableElement.querySelector('thead');
  const firstRow = tableElement.querySelector('tr');
  
  if (thead) {
    const ths = thead.querySelectorAll('th');
    ths.forEach(th => headers.push(th.textContent.trim()));
  } else if (firstRow) {
    // 如果没有 thead，从第一行获取表头
    const ths = firstRow.querySelectorAll('th');
    if (ths.length > 0) {
      ths.forEach(th => headers.push(th.textContent.trim()));
    } else {
      // 如果第一行没有 th，尝试从 td 获取
      const tds = firstRow.querySelectorAll('td');
      tds.forEach(td => headers.push(td.textContent.trim()));
    }
  }
  
  // 获取数据行
  const tbody = tableElement.querySelector('tbody');
  let bodyRows;
  
  if (tbody) {
    bodyRows = tbody.querySelectorAll('tr');
  } else {
    // 如果没有 tbody，获取所有 tr（排除第一行）
    const allRows = tableElement.querySelectorAll('tr');
    bodyRows = Array.from(allRows).slice(1);
  }
  
  bodyRows.forEach(tr => {
    const cells = tr.querySelectorAll('td');
    if (cells.length > 0) {
      const row = {};
      cells.forEach((td, index) => {
        if (headers[index]) {
          // 保留原始字符串格式（包括千分号、小数位等）
          // 图表渲染时由 TableWithChart 组件自行解析
          row[headers[index]] = td.textContent.trim();
        }
      });
      if (Object.keys(row).length > 0) {
        rows.push(row);
      }
    }
  });
  
  return { headers, rows };
};

const TableWrapper = memo(({ children }) => {
  const containerRef = useRef(null);
  const [tableData, setTableData] = useState(null);
  
  // 缓存 children 的 markdown 源码，用于比较是否变化
  const childrenMarkdownRef = useRef(null);

  useEffect(() => {
    // 立即解析表格
    if (containerRef.current) {
      const tableElement = containerRef.current.querySelector('table');
      if (tableElement) {
        const data = parseHtmlTable(tableElement);
        if (data.headers.length > 0 && data.rows.length > 0) {
          // 只有数据真正变化时才更新
          setTableData(prev => {
            const prevStr = JSON.stringify(prev);
            const currStr = JSON.stringify(data);
            return prevStr === currStr ? prev : data;
          });
        }
      }
    }
  }, []);

  // 有数据时渲染 TableWithChart，没有时渲染隐藏容器占位
  if (tableData) {
    return <TableWithChart headers={tableData.headers} rows={tableData.rows} />;
  }

  // 隐藏渲染 children 用于解析，但不显示（使用 opacity 保持占位）
  return (
    <div ref={containerRef} style={{ 
      opacity: 0,
      pointerEvents: 'none',
      userSelect: 'none'
    }}>
      {children}
    </div>
  );
});

TableWrapper.displayName = 'TableWrapper';

const MarkdownRenderer = memo(({ content }) => {
  if (!content) return null;

  // 缓存处理后的内容，避免每次渲染都执行 replace
  const processedContent = useMemo(() => {
    return content.replace(/```markdown\n?([\s\S]*?)\n?```/g, '$1');
  }, [content]);

  return (
    <div className="markdown-content">
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({node, ...props}) => {
            // 如果 p 标签内包含 pre 标签，则不渲染 p 标签（避免 HTML 验证警告）
            const children = props.children;
            if (children && typeof children === 'object' && children.type === 'pre') {
              return children;
            }
            return <p style={{ margin: '8px 0', lineHeight: 1.8 }} {...props} />;
          },
          h1: ({node, ...props}) => <h1 style={{ fontSize: '24px', fontWeight: 600, margin: '16px 0 8px', color: '#1890ff' }} {...props} />,
          h2: ({node, ...props}) => <h2 style={{ fontSize: '20px', fontWeight: 600, margin: '14px 0 6px', color: '#1890ff' }} {...props} />,
          h3: ({node, ...props}) => <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '12px 0 4px' }} {...props} />,
          ul: ({node, ...props}) => <ul style={{ margin: '8px 0', paddingLeft: '24px' }} {...props} />,
          ol: ({node, ...props}) => <ol style={{ margin: '8px 0', paddingLeft: '24px' }} {...props} />,
          li: ({node, ...props}) => <li style={{ margin: '4px 0', lineHeight: 1.6 }} {...props} />,
          blockquote: ({node, ...props}) => (
            <blockquote 
              style={{ 
                borderLeft: '4px solid #1890ff', 
                margin: '12px 0', 
                padding: '8px 16px', 
                background: '#f5f5f5',
                borderRadius: '0 4px 4px 0'
              }} 
              {...props} 
            />
          ),
          code: ({node, inline, ...props}) => {
            if (inline) {
              return (
                <code 
                  style={{ 
                    background: '#f5f5f5', 
                    padding: '2px 6px', 
                    borderRadius: '4px', 
                    fontSize: '0.9em',
                    color: '#c7254e'
                  }} 
                  {...props} 
                />
              );
            }
            return (
              <pre 
                style={{ 
                  background: '#282c34', 
                  color: '#abb2bf',
                  padding: '16px', 
                  borderRadius: '6px', 
                  overflow: 'auto',
                  margin: '12px 0',
                  fontSize: '14px',
                  lineHeight: 1.5
                }} 
              >
                <code {...props} />
              </pre>
            );
          },
          table: ({node, ...props}) => (
            <TableWrapper>
              <div style={{ overflow: 'auto', margin: '12px 0' }}>
                <table 
                  style={{ 
                    borderCollapse: 'collapse', 
                    width: '100%',
                    fontSize: '14px'
                  }} 
                  {...props} 
                />
              </div>
            </TableWrapper>
          ),
          th: ({node, ...props}) => (
            <th 
              style={{ 
                border: '1px solid #d9d9d9', 
                padding: '8px 12px', 
                background: '#fafafa',
                fontWeight: 600,
                textAlign: 'left'
              }} 
              {...props} 
            />
          ),
          td: ({node, ...props}) => (
            <td 
              style={{ 
                border: '1px solid #d9d9d9', 
                padding: '8px 12px' 
              }} 
              {...props} 
            />
          ),
          a: ({node, ...props}) => (
            <a 
              style={{ 
                color: '#1890ff', 
                textDecoration: 'none',
                borderBottom: '1px solid #1890ff'
              }} 
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
});

MarkdownRenderer.displayName = 'MarkdownRenderer';

export default MarkdownRenderer;
