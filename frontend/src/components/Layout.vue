<template>
  <n-layout position="absolute" style="height: 100vh">
    <!-- ═══════════════════════════════════════════════════════════ -->
    <!-- 顶部导航栏                                                   -->
    <!-- ═══════════════════════════════════════════════════════════ -->
    <n-layout-header
      bordered
      class="top-header"
      :style="{ height: '52px' }"
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
          <span class="logo-icon">📝</span>
          <span class="logo-text">NovelAI Writer</span>
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
        <n-button text @click="collapsed = !collapsed" class="desktop-only">
          <template #icon>
            <n-icon size="18">
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
    <n-layout has-sider position="absolute" style="top: 52px; bottom: 0">
      <!-- 桌面端侧边栏 -->
      <n-layout-sider
        bordered
        class="desktop-sider"
        content-style="padding: 8px; display: flex; flex-direction: column;"
        :width="siderWidth"
        :collapsed="collapsed"
        collapse-mode="width"
        @collapse="collapsed = true"
        @expand="collapsed = false"
      >
        <n-menu
          :value="activeKey"
          :collapsed="collapsed"
          :collapsed-width="64"
          :collapsed-icon-size="22"
          :options="menuOptions"
          :render-label="renderMenuLabel"
          @update:value="handleMenu"
        />

        <!-- 侧边栏底部信息 -->
        <div class="sider-footer" v-if="!collapsed">
          <n-divider />
          <n-text depth="3" style="font-size: 12px;">
            v0.1.0 · FastAPI + LangChain
          </n-text>
        </div>
      </n-layout-sider>

      <!-- 移动端抽屉菜单 -->
      <n-drawer
        v-model:show="mobileMenuOpen"
        :width="240"
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
        content-style="padding: 20px; overflow-y: auto;"
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
const siderWidth = computed(() => (isMobile.value ? 0 : 220))

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
      if (paths[2] === 'settings') items.push({ label: '⚙️ 设定' })
      else if (paths[2] === 'review') items.push({ label: '🔍 审核' })
      else if (paths[2] === 'characters') items.push({ label: '🎭 角色' })
      else if (paths[2] === 'world') items.push({ label: '🌍 世界观' })
      else if (paths[2] === 'factions') items.push({ label: '🏛️ 势力' })
      else if (paths[2] === 'outline') items.push({ label: '📜 大纲' })
      else if (paths[2] === 'dashboard') items.push({ label: '📊 仪表盘' })
      else if (paths[2] === 'knowledge') items.push({ label: '📚 知识库' })
      else if (paths[2] === 'memes') items.push({ label: '😂 热梗库' })
      else if (paths[2] === 'chat') items.push({ label: '💬 AI 对话' })
      else if (paths[2] === 'runs') items.push({ label: '🕐 运行记录' })
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
      label: '审核视图',
      key: `/projects/${id}/review`,
      icon: renderIcon(SearchOutline),
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
  label: '大纲编辑器',
  key: `/projects/${id}/outline`,
  icon: renderIcon(ListOutline),
  },
  {
  label: '项目仪表盘',
  key: `/projects/${id}/dashboard`,
  icon: renderIcon(StatsChartOutline),
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
  icon: renderIcon(TimeOutline),
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

/** 自定义菜单标签渲染 */
function renderMenuLabel(option) {
  if (option.type === 'divider') return option.label || ''
  return option.label
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
  padding: 0 16px;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.logo-icon {
  font-size: 22px;
}

.logo-text {
  color: #e94560;
  font-weight: 700;
  font-size: 17px;
  letter-spacing: 0.3px;
}

/* 面包屑 */
.desktop-breadcrumb {
  display: flex;
}

.breadcrumb-link {
  color: #9ca3af;
  text-decoration: none;
  transition: color 0.2s;
}
.breadcrumb-link:hover {
  color: #e94560;
}

.breadcrumb-current {
  color: #f3f4f6;
}

/* 移动端菜单按钮 */
.mobile-menu-btn {
  display: none;
}

/* ── 侧边栏 ──────────────────────────────────────────────────── */
.desktop-sider {
  transition: width 0.3s ease;
}

.sider-footer {
  margin-top: auto;
  padding: 8px;
  text-align: center;
}

/* ── 内容区 ──────────────────────────────────────────────────── */
.content-area {
  background: #f5f5f5;
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
    font-size: 15px;
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
