<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="themeOverrides">
    <n-message-provider placement="top-right">
      <n-notification-provider placement="top-right">
        <n-dialog-provider>
          <n-loading-bar-provider>
            <router-view />
          </n-loading-bar-provider>
        </n-dialog-provider>
      </n-notification-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { zhCN, dateZhCN } from 'naive-ui'

/**
 * 全局设计系统（NovelAI Writer · 创作工作台风格）
 * - 主色：紫罗兰 #6C5CE7（灵感 / 创造）
 * - 强调：暖琥珀 #F59E0B（AI 生成 / 亮点）
 * - 背景：暖白纸张 #F7F6F3，深色导航 #171C26
 */
const themeOverrides = {
  common: {
    primaryColor: '#6C5CE7',
    primaryColorHover: '#7E6FF0',
    primaryColorPressed: '#5B4BC9',
    primaryColorSuppl: '#8B7DF2',
    infoColor: '#3B82F6',
    successColor: '#10B981',
    warningColor: '#F59E0B',
    errorColor: '#EF4444',
    borderRadius: '10px',
    borderRadiusSmall: '7px',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif',
    fontSize: '14px',
    textColorBase: '#23272F',
    bodyColor: '#F7F6F3',
    cardColor: '#FFFFFF',
    borderColor: '#E8E6E0',
    dividerColor: '#EEECE6',
    boxShadow1: '0 1px 3px rgba(28, 24, 55, 0.06), 0 1px 2px rgba(28, 24, 55, 0.04)',
    boxShadow2: '0 4px 14px rgba(28, 24, 55, 0.08), 0 2px 4px rgba(28, 24, 55, 0.05)',
    boxShadow3: '0 12px 32px rgba(28, 24, 55, 0.12), 0 4px 8px rgba(28, 24, 55, 0.06)',
    popoverColor: '#FFFFFF',
  },
  Card: {
    borderRadius: '12px',
    titleFontWeight: '600',
    titleTextColor: '#1D2129',
  },
  Button: {
    borderRadiusMedium: '9px',
    borderRadiusSmall: '8px',
  },
  DataTable: {
    thColor: '#FAF9F6',
    thTextColor: '#6B7280',
    thFontWeight: '600',
    tdColorHover: '#F8F7FF',
  },
  Tag: {
    borderRadius: '999px',
  },
  Input: {
    borderRadius: '9px',
  },
  Drawer: {
    borderRadius: '14px 0 0 14px',
  },
  Modal: {
    borderRadius: '14px',
  },
  Tabs: {
    tabTextColorActiveLine: '#6C5CE7',
  },
  Menu: {
    itemTextColorActive: '#6C5CE7',
    itemIconColorActive: '#6C5CE7',
    itemColorActive: 'rgba(108, 92, 231, 0.10)',
    itemColorActiveHover: 'rgba(108, 92, 231, 0.14)',
    itemBorderRadius: '8px',
  },
}
</script>

<style>
* {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial,
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: #f7f6f3;
}

#app {
  height: 100vh;
  overflow: hidden;
}

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-thumb {
  border-radius: 4px;
  background: rgba(23, 28, 38, 0.18);
  border: 2px solid transparent;
  background-clip: content-box;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(23, 28, 38, 0.32);
  border: 2px solid transparent;
  background-clip: content-box;
}
::-webkit-scrollbar-track {
  background: transparent;
}

/* ── 通用页面头（各视图共用样式语言） ───────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 21px;
  flex-shrink: 0;
  background: linear-gradient(135deg, rgba(108, 92, 231, 0.14), rgba(245, 158, 11, 0.10));
  border: 1px solid rgba(108, 92, 231, 0.16);
}

.page-title h2 {
  margin: 0 0 3px 0;
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.2px;
  color: #1d2129;
}

.page-title .n-text {
  font-size: 13px;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* ── 卡片通用悬浮效果 ──────────────────────────────────────── */
.hover-card {
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.hover-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(28, 24, 55, 0.10), 0 3px 6px rgba(28, 24, 55, 0.05);
  border-color: rgba(108, 92, 231, 0.30);
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
