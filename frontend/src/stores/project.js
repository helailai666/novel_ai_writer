import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { projectAPI, chapterAPI, aiAPI, settingsAPI, reviewAPI, statsAPI } from '../api/index.js'

export const useProjectStore = defineStore('project', () => {
  const projects = ref([])
  const currentProject = ref(null)
  const chapters = ref([])
  const loading = ref(false)

  // 统计
  const stats = computed(() => ({
    total: projects.value.length,
    active: projects.value.filter(p => (p.progress || 0) < 100).length,
    done: projects.value.filter(p => (p.progress || 0) >= 100).length,
    words: projects.value.reduce((s, p) => s + (p.word_count || 0), 0),
  }))

  // 加载项目列表
  async function loadProjects() {
    loading.value = true
    try {
      const res = await projectAPI.getProjects()
      projects.value = res.data?.data || res.data || []
    } catch { projects.value = [] }
    finally { loading.value = false }
  }

  // 加载单个项目
  async function loadProject(id) {
    loading.value = true
    try {
      const [pRes, cRes] = await Promise.all([
        projectAPI.getProject(id),
        chapterAPI.getChapters(id).catch(() => ({ data: [] }))
      ])
      currentProject.value = pRes.data?.data || pRes.data
      chapters.value = cRes.data?.data || cRes.data || []
    } catch { currentProject.value = null; chapters.value = [] }
    finally { loading.value = false }
  }

  // 生成章节
  async function generateChapter(chapterNumber, title = '', wordCount = 2000) {
    const res = await aiAPI.generateContent(currentProject.value?.id, null, {
      chapter_number: chapterNumber, chapter_title: title, word_count: wordCount
    })
    await loadProject(currentProject.value?.id)
    return res.data
  }

  return { projects, currentProject, chapters, loading, stats, loadProjects, loadProject, generateChapter }
})
