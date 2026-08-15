import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/projects'
  },
  {
    path: '/projects',
    component: () => import('@/views/ProjectList.vue'),
    meta: { title: '项目列表' }
  },
  {
    path: '/projects/:id',
    component: () => import('@/components/Layout.vue'),
    meta: { title: '创作工作台' },
    children: [
      {
        path: '',
        name: 'ProjectDetail',
        component: () => import('@/views/ProjectDetail.vue'),
        meta: { title: '创作工作台' }
      },
      {
        path: 'settings',
        name: 'ProjectSettings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '模块设定' }
      },
      {
        path: 'review',
        name: 'ProjectReview',
        component: () => import('@/views/ReviewView.vue'),
        meta: { title: '审核视图' }
      },
      {
        path: 'characters',
        name: 'ProjectCharacters',
        component: () => import('@/views/CharactersView.vue'),
        meta: { title: '角色管理' }
      },
      {
        path: 'world',
        name: 'ProjectWorld',
        component: () => import('@/views/WorldSettingView.vue'),
        meta: { title: '世界观设定' }
      },
      {
        path: 'factions',
        name: 'ProjectFactions',
        component: () => import('@/views/FactionsView.vue'),
        meta: { title: '势力管理' }
      },
      {
        path: 'outline',
        name: 'ProjectOutline',
        component: () => import('@/views/OutlineView.vue'),
        meta: { title: '大纲编辑' }
      },
      {
        path: 'dashboard',
        name: 'ProjectDashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '项目仪表盘' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/projects'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} - NovelAI Writer`
    : 'NovelAI Writer'
})

export default router
