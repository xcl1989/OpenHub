import { useMemo, useRef, useCallback } from 'react';
import { prepare, layout, clearCache } from '@chenglou/pretext';

const DEFAULT_FONT = '15px Inter, -apple-system, BlinkMacSystemFont, sans-serif';
const DEFAULT_LINE_HEIGHT = 24;

export function usePretextMeasure(containerWidth = 600) {
  const cacheRef = useRef(new Map());

  const measureText = useCallback((text, options = {}) => {
    const { font = DEFAULT_FONT, lineHeight = DEFAULT_LINE_HEIGHT } = options;
    const cacheKey = `${text}|${font}|${lineHeight}|${containerWidth}`;

    if (cacheRef.current.has(cacheKey)) {
      return cacheRef.current.get(cacheKey);
    }

    try {
      const prepared = prepare(text, font);
      const result = layout(prepared, containerWidth, lineHeight);
      cacheRef.current.set(cacheKey, result);
      return result;
    } catch (error) {
      console.warn('[Pretext] measurement error:', error);
      return { height: 0, lineCount: 1 };
    }
  }, [containerWidth]);

  const clearMeasurementCache = useCallback(() => {
    cacheRef.current.clear();
    clearCache();
  }, []);

  return { measureText, clearMeasurementCache };
}

export function measureTextSync(text, containerWidth = 600, font = DEFAULT_FONT, lineHeight = DEFAULT_LINE_HEIGHT) {
  try {
    const prepared = prepare(text, font);
    return layout(prepared, containerWidth, lineHeight);
  } catch (error) {
    console.warn('[Pretext] measurement error:', error);
    return { height: 0, lineCount: 1 };
  }
}

export function estimateMessageHeight(message, containerWidth = 600) {
  const font = '15px Inter, -apple-system, BlinkMacSystemFont, sans-serif';
  const lineHeight = 24;
  
  let totalHeight = 0;
  const lines = [];

  if (message.reasoning) {
    const reasoning = message.reasoning;
    const result = measureTextSync(reasoning, containerWidth - 40, font, lineHeight);
    totalHeight += result.height + 60;
    lines.push({ type: 'reasoning', height: result.height });
  }

  if (message.content) {
    const result = measureTextSync(message.content, containerWidth - 40, font, lineHeight);
    totalHeight += result.height;
    lines.push({ type: 'content', height: result.height });
  }

  if (message.tools) {
    Object.entries(message.tools).forEach(([key, tool]) => {
      totalHeight += 100;
      lines.push({ type: 'tool', toolKey: key });
    });
  }

  if (message.images && message.images.length > 0) {
    const imageGridHeight = Math.ceil(message.images.length / 3) * 108 + 16;
    totalHeight += imageGridHeight;
    lines.push({ type: 'images', height: imageGridHeight });
  }

  totalHeight += 80;

  return { estimatedHeight: totalHeight, lines };
}

export function getBubbleWidth(contentLength, maxWidth = 600, minWidth = 200) {
  const charWidth = 8.5;
  const padding = 60;
  const estimatedWidth = contentLength * charWidth + padding;
  return Math.min(Math.max(estimatedWidth, minWidth), maxWidth);
}
