<template>
  <n-spin :show="loading">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">🔍</div>
        <div>
          <h2>项目审核</h2>
          <n-text depth="3">8 大维度审核 · 评分 0-100 · 问题与建议逐条列出</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-button type="primary" :loading="runningAll" @click="runAll">
          <template #icon><n-icon><SparklesOutline /></n-icon></template>
          运行全部维度
        </n-button>
      </div>
    </div>

    <n-grid :cols="isMobile ? 1 : 3" :x-gap="18" responsive="screen">
      <!-- ══ 待审核内容 ══ -->
      <n-grid-item span="3 m:1">
        <n-card class="review-card">
          <template #header>
            <span class="card-title">📄 待审核内容</span>
          </template>

          <n-form label-placement="top" size="small">
            <n-form-item label="选择章节（自动填充正文）">
              <n-select
                v-model:value="selectedChapterId"
                :options="chapterOptions"
                clearable
                filterable
                placeholder="选择要审核的章节"
                @update:value="onPickChapter"
              />
            </n-form-item>
            <n-form-item label="或直接粘贴正文">
              <n-input
                v-model:value="content"
                type="textarea"
                :rows="14"
                placeholder="粘贴要审核的章节正文..."
                class="content-area"
              />
            </n-form-item>
            <n-form-item label="补充上下文（章节梗概 / 设定提示，可选）">
              <n-input
                v-model:value="context"
                type="textarea"
                :rows="3"
                placeholder="如：本章是主角拜入宗门的场景，前文已铺垫主角出身孤儿..."
              />
            </n-form-item>
          </n-form>

          <n-alert v-if="!content.trim()" type="info" :bordered="false" style="margin-top: 4px">
            <template #header>💡 提示</template>
            选择一个章节或粘贴正文后，点击上方「运行全部维度」或右侧任意维度卡片。
          </n-alert>
        </n-card>
      </n-grid-item>

      <!-- ══ 维度网格 + 结果 ══ -->
      <n-grid-item span="3 m:2">
        <n-grid :cols="isMobile ? 1 : 2" :x-gap="14" :y-gap="14">
          <n-grid-item v-for="item in items" :key="item.key">
            <n-card
              class="dim-card hover-card"
              :class="{ 'is-running': item.loading }"
              @click="runOne(item)"
            >
              <template #header>
                <div class="dim-head">
                  <span class="dim-icon">{{ item.icon }}</span>
                  <span class="dim-label">{{ item.label }}</span>
                </div>
              </template>
              <template #header-extra>
                <n-spin v-if="item.loading" size="small" />
                <n-tag
                  v-else-if="item.result"
                  size="small"
                  :type="scoreTagType(item.result.score)"
                  :bordered="false"
                  round
                >
                  {{ item.result.score }} 分
                </n-tag>
                <n-tag v-else size="small" type="default" :bordered="false" round>待运行</n-tag>
              </template>
              <n-ellipsis :line-clamp="2" class="dim-desc">{{ item.desc }}</n-ellipsis>
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- ══ 结果面板 ══ -->
        <n-card v-if="currentResult" class="review-card" style="margin-top: 16px;">
          <template #header>
            <div class="result-head">
              <span class="card-title">{{ currentItem.icon }} {{ currentItem.label }} · 审核结果</span>
              <n-progress
                type="circle"
                :percentage="currentResult.score"
                :stroke-width="8"
                :color="scoreColor(currentResult.score)"
                :rail-color="'#F0EFEA'"
                style="width: 64px"
              />
            </div>
          </template>

          <n-text depth="2" style="display:block; margin-bottom: 12px;">{{ currentResult.summary }}</n-text>

          <template v-if="currentResult.highlights?.length">
            <div class="result-block">
              <div class="result-block-title">✨ 亮点</div>
              <ul class="result-list good">
                <li v-for="(hl, i) in currentResult.highlights" :key="i">{{ hl }}</li>
              </ul>
            </div>
          </template>

          <template v-if="currentResult.issues?.length">
            <div class="result-block">
              <div class="result-block-title">⚠️ 发现的问题</div>
              <ul class="result-list bad">
                <li v-for="(it, i) in currentResult.issues" :key="i">{{ it }}</li>
              </ul>
            </div>
          </template>

          <template v-if="currentResult.suggestions?.length">
            <div class="result-block">
              <div class="result-block-title">💡 改进建议</div>
              <ul class="result-list">
                <li v-for="(sg, i) in currentResult.suggestions" :key="i">{{ sg }}</li>
              </ul>
            </div>
          </template>

          <n-empty
            v-if="!currentResult.issues?.length && !currentResult.suggestions?.length && !currentResult.highlights?.length"
            description="该维度未返回详细条目" size="small"
          />
        </n-card>
      </n-grid-item>
    </n-grid>
  </n-spin>
</template>

<script setup>
/**
 * ReviewView.vue — 项目审核（适配后端 ReviewResponse: score/summary/issues/suggestions/highlights）
 * 维度端点: consistency/logic/foreshadowing/character-arc/pacing/prose/reader-perspective/comprehensive
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { SparklesOutline } from '@vicons/ionicons5'
import { reviewAPI, writingAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const pid = () => route.params.id

const isMobile = ref(false)
function checkScreen() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { checkScreen(); window.addEventListener('resize', checkScreen) })
onUnmounted(() => window.removeEventListener('resize', checkScreen))

const loading = ref(false)
const runningAll = ref(false)
const chapters = ref([])
const selectedChapterId = ref(null)
const content = ref('')
const context = ref('')
const currentItem = ref(null)
const currentResult = ref(null)

const chapterOptions = computed(() =>
  chapters.value.map((c) => ({
    label: `第${c.chapter_number}章 ${c.title || ''}`.trim(),
    value: c.id,
  }))
)

function onPickChapter(id) {
  const ch = chapters.value.find((c) => c.id === id)
  if (ch) {
    content.value = ch.content || ''
    if (!context.value) {
      context.value = `章节梗概：${ch.title || `第${ch.chapter_number}章`}`
    }
  }
}

const items = ref([
  { key: 'consistency', icon: '✅', label: '设定一致性', desc: '检查内容是否与所有设定匹配', result: null, loading: false },
  { key: 'logic', icon: '🧠', label: '逻辑检查', desc: '剧情逻辑 / 因果关系', result: null, loading: false },
  { key: 'foreshadowing', icon: '🔮', label: '伏笔追踪', desc: '伏笔设置与回收情况', result: null, loading: false },
  { key: 'character-arc', icon: '👤', label: '人物弧光', desc: '角色成长曲线一致性', result: null, loading: false },
  { key: 'pacing', icon: '📈', label: '节奏分析', desc: '爽点密度 / 冲突频率 / 高潮间隔', result: null, loading: false },
  { key: 'prose', icon: '✏️', label: '文笔评估', desc: '描写 / 对话 / 语法 / 语感评分', result: null, loading: false },
  { key: 'reader-perspective', icon: '👁️', label: '读者视角', desc: '阅读体验 / 情感共鸣', result: null, loading: false },
  { key: 'comprehensive', icon: '📊', label: '综合审核', desc: '汇总以上所有维度', result: null, loading: false },
])

function scoreTagType(score) {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'error'
}

function scoreColor(score) {
  if (score >= 80) return '#10B981'
  if (score >= 60) return '#F59E0B'
  return '#EF4444'
}

function assertContent() {
  if (!content.value.trim()) {
    message.warning('请先选择章节或粘贴待审核内容')
    return false
  }
  return true
}

async function runOne(item) {
  if (!assertContent() || item.loading) return
  item.loading = true
  currentItem.value = item
  currentResult.value = null
  try {
    const res = await reviewAPI.review(pid(), item.key, {
      content: content.value,
      context: context.value || undefined,
    })
    item.result = res.data
    currentResult.value = res.data
  } catch (e) {
    message.error(`${item.label}审核失败: ${e.message || '未知错误'}`)
  } finally {
    item.loading = false
  }
}

async function runAll() {
  if (!assertContent() || runningAll.value) return
  runningAll.value = true
  message.info('开始逐维度审核，请稍候…')
  try {
    for (const item of items.value) {
      item.loading = true
      try {
        const res = await reviewAPI.review(pid(), item.key, {
          content: content.value,
          context: context.value || undefined,
        })
        item.result = res.data
        currentItem.value = item
        currentResult.value = res.data
      } catch (e) {
        message.error(`${item.label}审核失败: ${e.message || ''}`)
      } finally {
        item.loading = false
      }
    }
    message.success('全部维度审核完成')
  } finally {
    runningAll.value = false
  }
}

async function loadChapters() {
  loading.value = true
  try {
    const res = await writingAPI.getChapters(pid())
    chapters.value = res.data?.data || res.data || []
  } catch {
    chapters.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadChapters)
</script>

<style scoped>
.review-card {
  border-radius: 14px;
}

.card-title {
  font-weight: 600;
  font-size: 15px;
}

.content-area {
  font-family: ui-serif, Georgia, 'Songti SC', serif;
  font-size: 14px;
  line-height: 1.9;
}

.dim-card {
  border-radius: 12px;
}

.dim-card.is-running {
  border-color: rgba(108, 92, 231, 0.4);
}

.dim-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dim-icon {
  font-size: 17px;
}

.dim-label {
  font-weight: 600;
  font-size: 14px;
}

.dim-desc {
  color: #6b7280;
  font-size: 12px;
}

.result-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.result-block {
  margin-top: 10px;
}

.result-block-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 6px;
}

.result-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.9;
  color: #4b5563;
}

.result-list.good li::marker {
  color: #10b981;
}

.result-list.bad li::marker {
  color: #ef4444;
}
</style>
