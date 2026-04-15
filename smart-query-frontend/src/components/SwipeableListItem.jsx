import React, { useState, useRef } from 'react';
import { Button } from 'antd';
import { InboxOutlined } from '@ant-design/icons';

const SwipeableListItem = ({ 
  children,
  sessionId, 
  isSelected,
  onClick,
  onArchive,
  ...props 
}) => {
  const [slideDistance, setSlideDistance] = useState(0);
  const touchStartX = useRef(0);
  const touchCurrentX = useRef(0);
  const SWIPE_THRESHOLD = 80;

  const handleTouchStart = (e) => {
    touchStartX.current = e.touches[0].clientX;
    touchCurrentX.current = touchStartX.current;
  };

  const handleTouchMove = (e) => {
    touchCurrentX.current = e.touches[0].clientX;
    const diff = touchStartX.current - touchCurrentX.current;
    if (diff > 0) {
      setSlideDistance(Math.min(diff, SWIPE_THRESHOLD));
    } else {
      setSlideDistance(Math.max(diff, 0));
    }
  };

  const handleTouchEnd = () => {
    if (slideDistance > SWIPE_THRESHOLD / 2) {
      onArchive();
    }
    setSlideDistance(0);
  };

  const handleClick = () => {
    if (slideDistance > 0) {
      setSlideDistance(0);
      return;
    }
    onClick();
  };

  return (
    <div 
      style={{ 
        position: 'relative', 
        marginBottom: 4,
        width: '100%',
        overflow: 'hidden',
        borderRadius: 8,
        background: '#fff'
      }}
    >
      <div
        style={{
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          width: SWIPE_THRESHOLD,
          background: '#ff4d4f',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1
        }}
      >
        <Button
          type="text"
          icon={<InboxOutlined />}
          onClick={(e) => { e.stopPropagation(); onArchive(); }}
          style={{ color: '#fff', fontSize: 20, padding: 0 }}
          title="归档会话"
        />
      </div>
      
      <div
        {...props}
        onClick={handleClick}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{
          padding: '6px 12px',
          cursor: sessionId ? 'pointer' : 'not-allowed',
          background: isSelected ? '#e6f7ff' : '#fff',
          border: isSelected ? '1px solid #1890ff' : '1px solid #e5e7eb',
          transition: slideDistance > 0 ? 'none' : 'all 0.2s',
          opacity: sessionId ? 1 : 0.6,
          transform: `translateX(${-slideDistance}px)`,
          touchAction: 'pan-y',
          position: 'relative',
          zIndex: 2,
          width: '100%',
          boxSizing: 'border-box'
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default SwipeableListItem;
