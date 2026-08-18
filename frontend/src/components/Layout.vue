<template>
  <n-layout position="absolute" style="height: 100vh">
    <!-- ═══════════════════════════════════════════════════════════ -->
    <!-- 顶部导航栏                                                   -->
    <!-- ═══════════════════════════════════════════════════════════ -->
    <n-layout-header
      bordered
      class="top-header"
      :style="{ height: '56px' }"
    >
      <div class="header-left">
        <!-- 移动端菜单按钮 -->
        <n-button
          class="mobile-menu-btn"
          text
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <template #icon>
            <n-icon size="20"><MenuOutline /></n-icon>
          </template>
        </n-button>

        <!-- Logo -->
        <div class="logo" @click="$router.push('/projects')">
          <div class="logo-mark">
            <n-icon :size="20"><CreateOutline /></n-icon>
          </div>
          <span class="logo-text">NovelAI<span class="logo-accent">Writer</span></span>
        </div>

        <!-- 桌面端面包屑 -->
        <n-breadcrumb class="desktop-breadcrumb">
          <n-breadcrumb-item
            v-for="(item, i) in breadcrumbs"
            :key="i"
          >
            <router-link
              v-if="item.path"
              :to="item.path"
              class="breadcrumb-link"
            >
              {{ item.label }}
            </router-link>
            <span v-else class="breadcrumb-current">{{ item.label }}</span>
          </n-breadcrumb-item>
        </n-breadcrumb>
      </div>

      <div class="header-right">
        <!-- 折叠按钮 -->
        <n-button text class="desktop-only" @click="collapsed = !collapsed">
          <template #icon>
            <n-icon size="18" color="#9CA3AF">
              <ChevronBackOutline v-if="!collapsed" />
              <ChevronForwardOutline v-else />
            </n-icon>
          </template>
        </n-button>
      </div>
    </n-layout-header>

    <!-- ═══════════════════════════════════════════════════════════ -->
    <!-- 主体区域                                                     -->
    <!-- ═══════════════════════════════════════════════════════════ -->
    <n-layout has-sider position="absolute" style="top: 56px; bottom: 0">
      <!-- 桌面端侧边栏 -->
      <n-layout-sider
        bordered
        class="desktop-sider"
        content-style="padding: 10px 8px; display: flex; flex-direction: column; gap: 8px;"
        :width="232"
        :collapsed="collapsed"
        collapse-mode="width"
        :collapsed-width="64"
        @collapse="collapsed = true"
        @expand="collapsed = false"
      >
        <!-- 项目信息卡 -->
        <div v-if="route.params.id && !collapsed" class="sider-project">
          <div class="sider-project-icon">📖</div>
          <div class="sider-project-body">
            <div class="sider-project-title">项目 #{{ String(route.params.id).slice(0, 8) }}</div>
            <div class="sider-project-sub">创作工作台</div>
          </div>
        </div>

        <n-menu
          :value="activeKey"
          :collapsed="collapsed"
          :collapsed-width="64"
          :collapsed-icon-size="20"
          :options="menuOptions"
          :indent="20"
          @update:value="handleMenu"
        />

        <!-- 侧边栏底部信息 -->
        <div class="sider-footer">
          <n-divider v-if="!collapsed" style="margin: 4px 0 10px" />
          <div v-if="!collapsed" class="sider-version">
            <span class="dot" /> v0.1.0 · FastAPI + LangGraph
          </div>
        </div>
      </n-layout-sider>

      <!-- 移动端抽屉菜单 -->
      <n-drawer
        v-model:show="mobileMenuOpen"
        :width="248"
        placement="left"
        :trap-focus="false"
      >
        <n-drawer-content title="导航菜单" :closable="true">
          <n-menu
            :value="activeKey"
            :options="menuOptions"
            @update:value="handleMobileMenu"
          />
        </n-drawer-content>
      </n-drawer>

      <!-- 内容区 -->
      <n-layout
        content-style="padding: 24px 28px 40px; overflow-y: auto;"
        class="content-area"
      >
        <router-view />
      </n-layout>
    </n-layout>
  </n-layout>
</template>

<script setup>
/**
 * Layout.vue — 全局布局组件
 *
 * 功能：
 * - 顶部导航栏：Logo + 面包屑 + 折叠按钮
 * - 左侧侧边栏：项目列表 | 新建项目 | 项目子页面（响应式折叠）
 * - 移动端适配：抽屉式菜单
 * - 响应式断点：<768px 自动折叠侧边栏
 */
import { ref, computed, h, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NIcon } from 'naive-ui'
import {
  MenuOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  CreateOutline,
  FolderOutline,
  AddCircleOutline,
  DocumentTextOutline,
  SettingsOutline,
  SearchOutline,
  BookOutline,
  PeopleOutline,
  GlobeOutline,
  BusinessOutline,
  ListOutline,
  StatsChartOutline,
  HappyOutline,
  TimeOutline,
  RibbonOutline,
  ChatbubblesOutline,
  FlagOutline,
  PulseOutline,
} from '@vicons/ionicons5'

const router = useRouter()
const route = useRoute()

// ── 状态 ────────────────────────────────────────────────────────
const collapsed = ref(false)
const mobileMenuOpen = ref(false)
const isMobile = ref(false)

// ── 响应式检测 ──────────────────────────────────────────────────
const MOBILE_BREAKPOINT = 768

function checkMobile() {
  isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
  if (isMobile.value && !collapsed.value) {
    collapsed.value = true
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

// ── 侧边栏宽度 ──────────────────────────────────────────────────
const siderWidth = computed(() => (isMobile.value ? 0 : 232))

// ── 当前激活菜单项 ──────────────────────────────────────────────
const activeKey = computed(() => {
  // 精确匹配子路由
  const path = route.path
  if (path.includes('/settings')) return path
  if (path.includes('/review')) return path
  return path
})

// ── 面包屑 ──────────────────────────────────────────────────────
const breadcrumbs = computed(() => {
  const paths = route.path.split('/').filter(Boolean)
  const items = [{ label: '🏠 首页', path: '/projects' }]

  if (paths[0] === 'projects') {
    if (paths[1] && paths[1] !== 'new') {
      items.push({
        label: `📖 项目 #${paths[1]}`,
        path: `/projects/${paths[1]}`,
      })
      const map = {
        settings: '⚙️ 设定',
        review: '🔍 审核',
        characters: '🎭 角色',
        world: '🌍 世界观',
        factions: '🏛️ 势力',
        outline: '📜 大纲',
        dashboard: '📊 仪表盘',
        knowledge: '📚 知识库',
        memes: '😂 热梗库',
        chat: '💬 AI 对话',
        timeline: '🕐 时间线',
        foreshadows: '🎯 伏笔管理',
        runs: '⚡ 运行记录',
      }
      if (map[paths[2]]) items.push({ label: map[paths[2]] })
    } else if (paths[1] === 'new') {
      items.push({ label: '➕ 新建项目' })
    }
  } else if (paths[0] === 'skills') {
    items.push({ label: '🎯 技能包' })
  } else if (paths[0] === 'settings') {
    items.push({ label: '⚙️ 全局设置' })
  }
  return items
})

// ── 菜单配置 ────────────────────────────────────────────────────

/** 基础菜单项（始终显示） */
const baseMenuOptions = [
  {
    label: '项目列表',
    key: '/projects',
    icon: renderIcon(FolderOutline),
  },
  {
    label: '新建项目',
    key: '/projects/new',
    icon: renderIcon(AddCircleOutline),
  },
]

/** 项目子页面菜单（在项目内时显示） */
const projectMenuOptions = computed(() => {
  if (!route.path.includes('/projects/') || !route.params.id) return []
  const id = route.params.id
  return [
    { type: 'divider', key: 'div-1' },
    {
      label: 'AI 对话',
      key: `/projects/${id}/chat`,
      icon: renderIcon(ChatbubblesOutline),
    },
    {
      label: '创作工作台',
      key: `/projects/${id}`,
      icon: renderIcon(DocumentTextOutline),
    },
    {
      label: '模块设定',
      key: `/projects/${id}/settings`,
      icon: renderIcon(SettingsOutline),
    },
    {
      label: '项目仪表盘',
      key: `/projects/${id}/dashboard`,
      icon: renderIcon(StatsChartOutline),
    },
    {
      label: '大纲编辑器',
      key: `/projects/${id}/outline`,
      icon: renderIcon(ListOutline),
    },
    {
      label: '角色管理',
      key: `/projects/${id}/characters`,
      icon: renderIcon(PeopleOutline),
    },
    {
      label: '世界观设定',
      key: `/projects/${id}/world`,
      icon: renderIcon(GlobeOutline),
    },
    {
      label: '势力管理',
      key: `/projects/${id}/factions`,
      icon: renderIcon(BusinessOutline),
    },
    {
      label: '时间线',
      key: `/projects/${id}/timeline`,
      icon: renderIcon(TimeOutline),
    },
    {
      label: '伏笔管理',
      key: `/projects/${id}/foreshadows`,
      icon: renderIcon(FlagOutline),
    },
    {
      label: '审核视图',
      key: `/projects/${id}/review`,
      icon: renderIcon(SearchOutline),
    },
    {
      label: '知识库',
      key: `/projects/${id}/knowledge`,
      icon: renderIcon(BookOutline),
    },
    {
      label: '热梗库',
      key: `/projects/${id}/memes`,
      icon: renderIcon(HappyOutline),
    },
    {
      label: '运行记录',
      key: `/projects/${id}/runs`,
      icon: renderIcon(PulseOutline),
    },
  ]
})

/** 底部菜单 */
const bottomMenuOptions = [
  { type: 'divider', key: 'div-2' },
  {
    label: '技能包',
    key: '/skills',
    icon: renderIcon(RibbonOutline),
  },
  {
    label: '全局设置',
    key: '/settings',
    icon: renderIcon(SettingsOutline),
  },
]

const menuOptions = computed(() => [
  ...baseMenuOptions,
  ...projectMenuOptions.value,
  ...bottomMenuOptions,
])

// ── 图标渲染 ────────────────────────────────────────────────────
function renderIcon(icon) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

// ── 导航处理 ────────────────────────────────────────────────────
function handleMenu(key) {
  router.push(key)
}

function handleMobileMenu(key) {
  mobileMenuOpen.value = false
  handleMenu(key)
}
</script>

<style scoped>
/* ── 顶部导航 ─────────────────────────────────────────────────── */
.top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: linear-gradient(120deg, #171c26 0%, #1f2636 55%, #232a3d 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.header-right {
  display: flex;
  align-items: center;
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.logo-mark {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #6c5ce7 0%, #8b5cf6 100%);
  box-shadow: 0 3px 8px rgba(108, 92, 231, 0.35);
}

.logo-text {
  color: #f3f4f6;
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 0.3px;
}

.logo-accent {
  color: #a78bfa;
  margin-left: 4px;
}

/* 面包屑 */
.desktop-breadcrumb {
  display: flex;
  margin-left: 6px;
  padding-left: 14px;
  border-left: 1px solid rgba(255, 255, 255, 0.10);
}

.breadcrumb-link {
  color: #9ca3af;
  text-decoration: none;
  font-size: 13px;
  transition: color 0.2s;
}
.breadcrumb-link:hover {
  color: #a78bfa;
}

.breadcrumb-current {
  color: #e5e7eb;
  font-size: 13px;
}

/* 移动端菜单按钮 */
.mobile-menu-btn {
  display: none;
  color: #d1d5db;
}

/* ── 侧边栏 ──────────────────────────────────────────────────── */
.desktop-sider {
  transition: width 0.3s ease;
  background: #fbfaf8;
}

.sider-project {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin: 2px 4px 6px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(108, 92, 231, 0.10), rgba(245, 158, 11, 0.06));
  border: 1px solid rgba(108, 92, 231, 0.14);
}

.sider-project-icon {
  font-size: 20px;
}

.sider-project-body {
  min-width: 0;
}

.sider-project-title {
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sider-project-sub {
  font-size: 11px;
  color: #8a8f98;
}

.sider-footer {
  margin-top: auto;
  padding: 0 8px 4px;
}

.sider-version {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #9ca3af;
  font-size: 11px;
}

.sider-version .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
}

/* ── 内容区 ──────────────────────────────────────────────────── */
.content-area {
  background: #f7f6f3;
}

/* ── 响应式 ──────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .desktop-sider {
    display: none !important;
  }

  .desktop-breadcrumb {
    display: none;
  }

  .desktop-only {
    display: none !important;
  }

  .mobile-menu-btn {
    display: inline-flex;
  }

  .logo-text {
    font-size: 14px;
  }
}

@media (min-width: 769px) {
  .mobile-menu-btn {
    display: none;
  }
}

/* ── 滚动条 ──────────────────────────────────────────────────── */
:deep(.n-layout-sider-scroll-container) {
  display: flex;
  flex-direction: column;
  height: 100%;
}
</style>
