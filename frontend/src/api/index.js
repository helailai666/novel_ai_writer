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
  getProjects(params) {
    // 必须带尾斜杠：后端只注册了 /api/projects/，不带斜杠会触发 307 重定向
    // 到绝对地址 http://localhost:18000/api/projects/，产生跨域请求并可能被 CORS 拦截
    return http.get('/projects/', { params })
  },
  getProject(id) {
    return http.get(`/projects/${id}`)
  },
  createProject(data) {
    return http.post('/projects/', data)
  },
  updateProject(id, data) {
    return http.patch(`/projects/${id}`, data)
  },
  deleteProject(id) {
    return http.delete(`/projects/${id}`)
  },
  exportProject(id, format = 'txt') {
    return http.get(`/projects/${id}/export`, { params: { format }, responseType: 'blob' })
  },
  importProject(backup) {
    return http.post('/projects/import', { backup })
  }
}

// ─── 写作 API（章节 + 卷）────────────────────────────
export const writingAPI = {
  // 卷
  getVolumes(projectId) {
    return http.get(`/projects/${projectId}/writing/volumes`)
  },
  createVolume(projectId, data) {
    return http.post(`/projects/${projectId}/writing/volumes`, data)
  },
  deleteVolume(projectId, volumeId) {
    return http.delete(`/projects/${projectId}/writing/volumes/${volumeId}`)
  },
  // 章节
  getChapters(projectId, params) {
    return http.get(`/projects/${projectId}/writing/chapters`, { params })
  },
  getChapter(projectId, chapterId) {
    return http.get(`/projects/${projectId}/writing/chapters/${chapterId}`)
  },
  createChapter(projectId, data) {
    return http.post(`/projects/${projectId}/writing/chapters`, data)
  },
  updateChapter(projectId, chapterId, data) {
    return http.patch(`/projects/${projectId}/writing/chapters/${chapterId}`, data)
  },
  deleteChapter(projectId, chapterId) {
    return http.delete(`/projects/${projectId}/writing/chapters/${chapterId}`)
  }
}

// ─── AI 创作 API ─────────────────────────────────────
export const aiAPI = {
  /** 非流式生成 */
  generateContent(projectId, params) {
    return http.post(`/projects/${projectId}/writing/generate`, params)
  },
  /** 流式生成（SSE） */
  generateStream(projectId, params) {
    return fetch(`/api/projects/${projectId}/writing/generate-stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    })
  },
  /** 批量生成 */
  batchGenerate(projectId, params) {
    return http.post(`/projects/${projectId}/writing/batch-generate`, params)
  },
  /** 续写 */
  continueWriting(projectId, params) {
    return http.post(`/projects/${projectId}/writing/continue`, params)
  },
  /** 润色 */
  polish(projectId, params) {
    return http.post(`/projects/${projectId}/writing/polish`, params)
  }
}

// ─── 设定 API（各模块独立端点）────────────────────────
export const settingsAPI = {
  // 世界设定
  getWorldSettings(projectId) {
    return http.get(`/projects/${projectId}/settings/world`)
  },
  createWorldSetting(projectId, data) {
    return http.post(`/projects/${projectId}/settings/world`, data)
  },
  updateWorldSetting(projectId, settingId, data) {
    return http.patch(`/projects/${projectId}/settings/world/${settingId}`, data)
  },
  deleteWorldSetting(projectId, settingId) {
    return http.delete(`/projects/${projectId}/settings/world/${settingId}`)
  },
  // 角色
  getCharacters(projectId) {
    return http.get(`/projects/${projectId}/settings/characters`)
  },
  getCharacter(projectId, charId) {
    return http.get(`/projects/${projectId}/settings/characters/${charId}`)
  },
  createCharacter(projectId, data) {
    return http.post(`/projects/${projectId}/settings/characters`, data)
  },
  updateCharacter(projectId, charId, data) {
    return http.patch(`/projects/${projectId}/settings/characters/${charId}`, data)
  },
  deleteCharacter(projectId, charId) {
    return http.delete(`/projects/${projectId}/settings/characters/${charId}`)
  },
  // 技能
  getSkills(projectId) {
    return http.get(`/projects/${projectId}/settings/skills`)
  },
  createSkill(projectId, data) {
    return http.post(`/projects/${projectId}/settings/skills`, data)
  },
  deleteSkill(projectId, skillId) {
    return http.delete(`/projects/${projectId}/settings/skills/${skillId}`)
  },
  // 道具
  getItems(projectId) {
    return http.get(`/projects/${projectId}/settings/items`)
  },
  createItem(projectId, data) {
    return http.post(`/projects/${projectId}/settings/items`, data)
  },
  deleteItem(projectId, itemId) {
    return http.delete(`/projects/${projectId}/settings/items/${itemId}`)
  },
  // 势力
  getFactions(projectId) {
    return http.get(`/projects/${projectId}/settings/factions`)
  },
  createFaction(projectId, data) {
    return http.post(`/projects/${projectId}/settings/factions`, data)
  },
  deleteFaction(projectId, factionId) {
    return http.delete(`/projects/${projectId}/settings/factions/${factionId}`)
  },
  // 大纲
  getOutlines(projectId) {
    return http.get(`/projects/${projectId}/settings/outlines`)
  },
  createOutline(projectId, data) {
    return http.post(`/projects/${projectId}/settings/outlines`, data)
  },
  updateOutline(projectId, outlineId, data) {
    return http.patch(`/projects/${projectId}/settings/outlines/${outlineId}`, data)
  },
  deleteOutline(projectId, outlineId) {
    return http.delete(`/projects/${projectId}/settings/outlines/${outlineId}`)
  },
  // 场景/地点
  getLocations(projectId) {
    return http.get(`/projects/${projectId}/settings/locations`)
  },
  createLocation(projectId, data) {
    return http.post(`/projects/${projectId}/settings/locations`, data)
  },
  deleteLocation(projectId, locationId) {
    return http.delete(`/projects/${projectId}/settings/locations/${locationId}`)
  },
  // 时间线
  getTimelines(projectId) {
    return http.get(`/projects/${projectId}/settings/timelines`)
  },
  createTimeline(projectId, data) {
    return http.post(`/projects/${projectId}/settings/timelines`, data)
  },
  updateTimeline(projectId, timelineId, data) {
    return http.patch(`/projects/${projectId}/settings/timelines/${timelineId}`, data)
  },
  deleteTimeline(projectId, timelineId) {
    return http.delete(`/projects/${projectId}/settings/timelines/${timelineId}`)
  },
  // 伏笔
  getForeshadows(projectId) {
    return http.get(`/projects/${projectId}/settings/foreshadows`)
  },
  createForeshadow(projectId, data) {
    return http.post(`/projects/${projectId}/settings/foreshadows`, data)
  },
  updateForeshadow(projectId, foreshadowId, data) {
    return http.patch(`/projects/${projectId}/settings/foreshadows/${foreshadowId}`, data)
  },
  deleteForeshadow(projectId, foreshadowId) {
    return http.delete(`/projects/${projectId}/settings/foreshadows/${foreshadowId}`)
  },
  audit(projectId) {
    return http.post(`/projects/${projectId}/settings/audit`)
  }
}

// ─── AI 辅助生成设定 API ─────────────────────────────
export const aiGenerateAPI = {
  generateWorld(projectId, data) {
    return http.post(`/projects/${projectId}/settings/ai/generate-world`, data)
  },
  generateCharacter(projectId, data) {
    return http.post(`/projects/${projectId}/settings/ai/generate-character`, data)
  },
  generateItem(projectId, data) {
    return http.post(`/projects/${projectId}/settings/ai/generate-item`, data)
  },
  generateSkill(projectId, data) {
    return http.post(`/projects/${projectId}/settings/ai/generate-skill`, data)
  },
  generateFaction(projectId, data) {
    return http.post(`/projects/${projectId}/settings/ai/generate-faction`, data)
  },
  generateLocation(projectId, data) {
    return http.post(`/projects/${projectId}/settings/ai/generate-location`, data)
  },
  generateOutline(projectId, data) {
    return http.post(`/projects/${projectId}/settings/ai/generate-outline`, data)
  },
  generateTimeline(projectId, data) {
    return http.post(`/projects/${projectId}/settings/ai/generate-timeline`, data)
  }
}

// ─── 审核 API ────────────────────────────────────────
export const reviewAPI = {
  /** 通用审核（dimension: consistency/logic/foreshadowing/character-arc/pacing/prose/reader-perspective/comprehensive） */
  review(projectId, dimension, data) {
    return http.post(`/review/${dimension}`, { project_id: projectId, ...data })
  },
  /** 一致性检查 */
  checkConsistency(projectId, content, context) {
    return http.post('/review/consistency', { project_id: projectId, content, context })
  },
  /** 逻辑检查 */
  checkLogic(projectId, content, context) {
    return http.post('/review/logic', { project_id: projectId, content, context })
  },
  /** 伏笔检查 */
  checkForeshadowing(projectId, content, context) {
    return http.post('/review/foreshadowing', { project_id: projectId, content, context })
  },
  /** 角色弧光检查 */
  checkCharacterArc(projectId, content, context) {
    return http.post('/review/character-arc', { project_id: projectId, content, context })
  },
  /** 节奏检查 */
  checkPacing(projectId, content, context) {
    return http.post('/review/pacing', { project_id: projectId, content, context })
  },
  /** 文笔检查 */
  checkProse(projectId, content, context) {
    return http.post('/review/prose', { project_id: projectId, content, context })
  },
  /** 读者视角检查 */
  checkReaderPerspective(projectId, content, context) {
    return http.post('/review/reader-perspective', { project_id: projectId, content, context })
  },
  /** 综合审核 */
  checkComprehensive(projectId, content, context) {
    return http.post('/review/comprehensive', { project_id: projectId, content, context })
  }
}

// ─── 搜索 API ────────────────────────────────────────
export const searchAPI = {
  searchProjects(q, limit) {
    return http.get('/search/projects', { params: { q, limit } })
  },
  searchCharacters(projectId, q) {
    return http.get(`/search/projects/${projectId}/characters`, { params: { q } })
  },
  searchChapters(projectId, q) {
    return http.get(`/search/projects/${projectId}/chapters`, { params: { q } })
  },
  searchWeb(query, max_results) {
    return http.post('/search/web', { query, max_results })
  },
  searchWebAISummary(query, max_results) {
    return http.post('/search/web/ai-summary', { query, max_results })
  }
}

// ─── 知识库 API ─────────────────────────────────────────
export const knowledgeAPI = {
  listDocs(projectId, params) {
    return http.get('/knowledge', { params: { project_id: projectId, ...params } })
  },
  getDoc(docId) {
    return http.get(`/knowledge/${docId}`)
  },
  createDoc(data, projectId) {
    return http.post('/knowledge', data, { params: { project_id: projectId } })
  },
  updateDoc(docId, data) {
    return http.put(`/knowledge/${docId}`, data)
  },
  ingestText(data, projectId) {
    return http.post('/knowledge/ingest', null, { params: { ...data, project_id: projectId } })
  },
  uploadFile(file, projectId) {
    const form = new FormData()
    form.append('file', file)
    return http.post('/knowledge/upload', form, { params: { project_id: projectId } })
  },
  deleteDoc(docId) {
    return http.delete(`/knowledge/${docId}`)
  },
  search(query, projectId, opts) {
    return http.post('/knowledge/search', { query, ...opts }, { params: { project_id: projectId } })
  }
}

// ─── 热梗 API ───────────────────────────────────────────
export const hotMemeAPI = {
  list(projectId, params) {
    return http.get('/hot-memes', { params: { project_id: projectId, ...params } })
  },
  create(data, projectId) {
    return http.post('/hot-memes', data, { params: { project_id: projectId } })
  },
  update(memeId, data) {
    return http.put(`/hot-memes/${memeId}`, data)
  },
  search(q, projectId) {
    return http.get('/hot-memes/search', { params: { q, project_id: projectId } })
  },
  remove(memeId) {
    return http.delete(`/hot-memes/${memeId}`)
  }
}

// ─── Agent API（LangGraph）──────────────────────────────
export const agentsAPI = {
  chat(data, signal) {
    return fetch('/api/agents/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      signal
    })
  },
  run(data) {
    return http.post('/agents/run', data)
  },
  listRuns(params) {
    return http.get('/agents/runs', { params })
  },
  getRun(runId) {
    return http.get(`/agents/runs/${runId}`)
  },
  deleteRun(runId) {
    return http.delete(`/agents/runs/${runId}`)
  },
  retryRun(runId) {
    return http.post(`/agents/runs/${runId}/retry`)
  },
  clearRuns(params) {
    return http.delete('/agents/runs', { params })
  },
  chatHistory(params) {
    return http.get('/agents/chat/history', { params })
  }
}

// ─── Tools / Skills / 模型供应商 API ────────────────────
export const toolsAPI = {
  list() {
    return http.get('/tools')
  },
  call(name, arguments_) {
    return http.post('/tools/call', { name, arguments: arguments_ })
  }
}

export const skillsAPI = {
  list() {
    return http.get('/skills')
  },
  get(name) {
    return http.get(`/skills/${name}`)
  },
  apply(name) {
    return http.post(`/skills/${name}/apply`)
  },
  create(data) {
    return http.post('/skills', data)
  },
  update(name, data) {
    return http.put(`/skills/${name}`, data)
  },
  remove(name) {
    return http.delete(`/skills/${name}`)
  },
  setEnabled(name, enabled) {
    return http.patch(`/skills/${name}/enabled`, { enabled })
  }
}

export const providerAPI = {
  list() {
    return http.get('/model-providers')
  },
  create(data) {
    return http.post('/model-providers', data)
  },
  update(id, data) {
    return http.patch(`/model-providers/${id}`, data)
  },
  remove(id) {
    return http.delete(`/model-providers/${id}`)
  },
  test(data) {
    return http.post('/model-providers/test', data)
  }
}

// ─── MCP API ────────────────────────────────────────────
export const mcpAPI = {
  servers() {
    return http.get('/mcp/servers')
  },
  reload() {
    return http.post('/mcp/reload')
  },
  tools() {
    return http.get('/mcp/tools')
  }
}

// ─── 缓存 / 运行时配置 API（J 轮可观测性）────────────────
export const cacheAPI = {
  stats() {
    return http.get('/cache/stats')
  },
  clear() {
    return http.post('/cache/clear')
  }
}

export const runtimeAPI = {
  config() {
    return http.get('/runtime/config')
  }
}

// 默认导出（快捷调用）
export default {
  ...projectAPI,
  ...writingAPI,
  ...aiAPI,
  ...settingsAPI,
  ...aiGenerateAPI,
  ...reviewAPI,
  ...searchAPI,
  ...knowledgeAPI,
  ...hotMemeAPI,
  ...agentsAPI,
  ...toolsAPI,
  ...skillsAPI,
  ...providerAPI,
  ...mcpAPI,
  ...cacheAPI,
  ...runtimeAPI
}
