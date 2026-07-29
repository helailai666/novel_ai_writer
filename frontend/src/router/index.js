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
      }
    ]
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
