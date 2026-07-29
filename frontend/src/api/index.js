import axios from 'axios'
import { useMessage } from 'naive-ui'

const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器
http.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
)

// 响应拦截器：统一错误提示
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.detail
      || error.response?.data?.message
      || error.message
      || '网络错误'
    // 仅在浏览器端弹提示
    if (typeof window !== 'undefined') {
      try {
        const message = useMessage()
        message?.error(msg)
      } catch (_) { /* 忽略非组件上下文 */ }
    }
    return Promise.reject(error)
  }
)

// ─── 项目 API ────────────────────────────────────────
export const projectAPI = {
  /** 获取项目列表 */
  getProjects(params) {
    return http.get('/projects', { params })
  },
  /** 获取单个项目 */
  getProject(id) {
    return http.get(`/projects/${id}`)
  },
  /** 创建项目 */
  createProject(data) {
    return http.post('/projects/', data)
  },
  /** 更新项目 */
  updateProject(id, data) {
    return http.put(`/projects/${id}`, data)
  },
  /** 删除项目 */
  deleteProject(id) {
    return http.delete(`/projects/${id}`)
  },
  /** 导出项目 */
  exportProject(id, format = 'txt') {
    return http.get(`/projects/${id}/export`, { params: { format }, responseType: 'blob' })
  }
}

// ─── 章节 API ────────────────────────────────────────
export const chapterAPI = {
  /** 获取章节列表 */
  getChapters(projectId) {
    return http.get(`/projects/${projectId}/chapters`)
  },
  /** 获取单个章节 */
  getChapter(chapterId) {
    return http.get(`/chapters/${chapterId}`)
  },
  /** 创建章节 */
  createChapter(projectId, data) {
    return http.post(`/projects/${projectId}/chapters`, data)
  },
  /** 更新章节 */
  updateChapter(chapterId, data) {
    return http.put(`/chapters/${chapterId}`, data)
  },
  /** 删除章节 */
  deleteChapter(chapterId) {
    return http.delete(`/chapters/${chapterId}`)
  },
  /** 排章节序 */
  reorderChapters(projectId, chapterIds) {
    return http.put(`/projects/${projectId}/chapters/reorder`, { chapter_ids: chapterIds })
  }
}

// ─── AI 创作 API ─────────────────────────────────────
export const aiAPI = {
  /** 生成段落内容 */
  generateContent(projectId, chapterId, params) {
    return http.post(`/projects/${projectId}/chapters/${chapterId}/generate`, params)
  },
  /** 流式生成（SSE）— 对齐后端 /api/projects/{id}/writing/generate-stream */
  generateStream(projectId, params) {
    return fetch(`/api/projects/${projectId}/writing/generate-stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    })
  },
  /** 生成大纲 */
  generateOutline(projectId, params) {
    return http.post(`/projects/${projectId}/outline/generate`, params)
  },
  /** 续写 */
  continueWriting(projectId, chapterId, params) {
    return http.post(`/projects/${projectId}/chapters/${chapterId}/continue`, params)
  },
  /** 润色 */
  polish(projectId, chapterId, params) {
    return http.post(`/projects/${projectId}/chapters/${chapterId}/polish`, params)
  },
  /** 扩写/缩写 */
  expandOrShorten(projectId, chapterId, params) {
    return http.post(`/projects/${projectId}/chapters/${chapterId}/expand`, params)
  }
}

// ─── 设定 API（12 模块）──────────────────────────────
export const settingsAPI = {
  /** 获取所有模块设定 */
  getSettings(projectId) {
    return http.get(`/projects/${projectId}/settings`)
  },
  /** 保存模块设定 */
  saveSettings(projectId, settings) {
    return http.put(`/projects/${projectId}/settings`, settings)
  },
  /** 获取单个模块设定 */
  getModuleSettings(projectId, moduleKey) {
    return http.get(`/projects/${projectId}/settings/${moduleKey}`)
  },
  /** 保存单个模块设定 */
  saveModuleSettings(projectId, moduleKey, data) {
    return http.put(`/projects/${projectId}/settings/${moduleKey}`, data)
  },
  /** AI 辅助生成设定 */
  generateSettings(projectId, moduleKey) {
    return http.post(`/projects/${projectId}/settings/${moduleKey}/generate`)
  }
}

// ─── 审核 API ────────────────────────────────────────
export const reviewAPI = {
  /** 审核内容 */
  reviewContent(projectId, data) {
    return http.post(`/projects/${projectId}/review`, data)
  },
  /** 获取审核记录 */
  getReviewHistory(projectId) {
    return http.get(`/projects/${projectId}/review/history`)
  },
  /** 纠错建议 */
  getSuggestions(projectId, content) {
    return http.post(`/projects/${projectId}/review/suggestions`, { content })
  },
  /** 一致性检查 */
  checkConsistency(projectId) {
    return http.post(`/projects/${projectId}/review/consistency`)
  }
}

// ─── 角色 API ────────────────────────────────────────
export const characterAPI = {
  getCharacters(projectId) {
    return http.get(`/projects/${projectId}/characters`)
  },
  createCharacter(projectId, data) {
    return http.post(`/projects/${projectId}/characters`, data)
  },
  updateCharacter(characterId, data) {
    return http.put(`/characters/${characterId}`, data)
  },
  deleteCharacter(characterId) {
    return http.delete(`/characters/${characterId}`)
  }
}

// ─── 世界设定 API ────────────────────────────────────
export const worldAPI = {
  getWorldSettings(projectId) {
    return http.get(`/projects/${projectId}/world`)
  },
  saveWorldSettings(projectId, data) {
    return http.put(`/projects/${projectId}/world`, data)
  }
}

// ─── 搜索结果/灵感 API ───────────────────────────────
export const inspirationAPI = {
  getInspirations(projectId) {
    return http.get(`/projects/${projectId}/inspirations`)
  },
  createInspiration(projectId, data) {
    return http.post(`/projects/${projectId}/inspirations`, data)
  }
}

// ─── 统计 API ────────────────────────────────────────
export const statsAPI = {
  getProjectStats(projectId) {
    return http.get(`/projects/${projectId}/stats`)
  },
  getDashboardStats() {
    return http.get('/stats/dashboard')
  }
}

// 默认导出（快捷调用）
export default {
  ...projectAPI,
  ...chapterAPI,
  ...aiAPI,
  ...settingsAPI,
  ...reviewAPI,
  ...characterAPI,
  ...worldAPI,
  ...inspirationAPI,
  ...statsAPI
}
