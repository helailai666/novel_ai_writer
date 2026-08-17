<template>
  <n-spin :show="loading">
    <div class="page-header">
      <div class="page-title">
        <h2>📚 知识库</h2>
        <n-text depth="3">文档资料 · 设定参考 · 全局/项目知识（混合检索）</n-text>
      </div>
      <n-space>
        <n-button @click="openSearch = true" type="info" ghost>
          <template #icon><n-icon><SearchOutline /></n-icon></template>
          检索
        </n-button>
        <n-button @click="showIngest = true" type="primary">
          <template #icon><n-icon><CloudUploadOutline /></n-icon></template>
          导入知识
        </n-button>
      </n-space>
    </div>

    <!-- 文档列表 -->
    <n-data-table
      :columns="columns"
      :data="docs"
      :pagination="pagination"
      :row-key="(row) => row.id"
      :loading="loading"
    />

    <!-- 检索结果抽屉 -->
    <n-drawer v-model:show="openSearch" :width="520" placement="right">
      <n-drawer-content title="🔍 知识检索">
        <n-input v-model:value="searchQuery" placeholder="输入检索词…" @keyup.enter="doSearch">
          <template #suffix>
            <n-button size="tiny" type="primary" ghost @click="doSearch">检索</n-button>
          </template>
        </n-input>
        <n-empty v-if="!searchResults.length" description="输入关键词开始检索" style="margin-top:32px" />
        <n-card
          v-for="(d, i) in searchResults"
          :key="i"
          size="small"
          style="margin-top:12px"
        >
          <template #header>
            <n-space align="center" justify="space-between" style="width:100%">
              <b>{{ d.title }}</b>
              <n-tag size="tiny" type="info">{{ d.category }}</n-tag>
            </n-space>
          </template>
          <n-text depth="2">{{ d.content }}</n-text>
          <template v-if="d.phrase" #footer>
            <n-text depth="3">热梗：{{ d.phrase }} — {{ d.meaning }}</n-text>
          </template>
        </n-card>
      </n-drawer-content>
    </n-drawer>

    <!-- 导入抽屉 -->
    <n-drawer v-model:show="showIngest" :width="560" placement="right">
      <n-drawer-content title="📥 导入知识">
        <n-form label-placement="top">
          <n-form-item label="文本摄取">
            <n-input v-model:value="ingest.title" placeholder="标题" style="margin-bottom:8px" />
            <n-input v-model:value="ingest.content" type="textarea" :rows="5" placeholder="内容（自动切片并向量化）" />
            <n-space style="margin-top:8px">
              <n-input v-model:value="ingest.category" placeholder="类别(general/history/worldview…)" style="width:220px" />
              <n-input v-model:value="ingest.tags" placeholder="标签(逗号分隔)" />
            </n-space>
          </n-form-item>
          <n-form-item label="文件上传（txt/md）">
            <n-upload :show-file-list="false" :custom-request="handleUpload">
              <n-button>选择文件</n-button>
            </n-upload>
          </n-form-item>
          <n-space justify="end">
            <n-button type="primary" :loading="ingestLoading" @click="doIngest">导入</n-button>
          </n-space>
        </n-form>
      </n-drawer-content>
    </n-drawer>
  </n-spin>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { SearchOutline, CloudUploadOutline, TrashOutline } from '@vicons/ionicons5'
import { knowledgeAPI } from '../api/index.js'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const projectId = computed(() => route.params.id)

const loading = ref(false)
const docs = ref([])
const searchQuery = ref('')
const searchResults = ref([])
const openSearch = ref(false)
const showIngest = ref(false)
const ingestLoading = ref(false)
const ingest = reactive({ title: '', content: '', category: 'general', tags: '' })

const pagination = { pageSize: 20 }

const columns = [
  { title: '标题', key: 'title', ellipsis: { tooltip: true } },
  { title: '类别', key: 'category', width: 120, render: (r) => h('n-tag', { size: 'tiny', type: 'info' }, { default: () => r.category }) },
  { title: '来源', key: 'source', width: 140 },
  { title: '更新时间', key: 'updated_at', width: 180 },
  {
    title: '操作', key: 'actions', width: 90,
    render: (r) => h('n-button', { size: 'tiny', quaternary: true, type: 'error', onClick: () => removeDoc(r) }, { icon: () => h('n-icon', null, { default: () => h(TrashOutline) }) }),
  },
]

onMounted(loadDocs)

async function loadDocs() {
  loading.value = true
  try {
    const res = await knowledgeAPI.listDocs(projectId.value)
    docs.value = res.data
  } catch (e) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function doSearch() {
  if (!searchQuery.value.trim()) return
  const res = await knowledgeAPI.search(searchQuery.value.trim(), projectId.value, { top_k: 8 })
  searchResults.value = [...(res.data.docs || []), ...(res.data.memes || [])]
}

async function doIngest() {
  if (!ingest.title || !ingest.content) {
    message.warning('请填写标题与内容')
    return
  }
  ingestLoading.value = true
  try {
    await knowledgeAPI.ingestText({ ...ingest }, projectId.value)
    message.success('知识已导入并索引')
    showIngest.value = false
    loadDocs()
  } catch (e) {
    message.error(e.message || '导入失败')
  } finally {
    ingestLoading.value = false
  }
}

async function handleUpload({ file }) {
  try {
    await knowledgeAPI.uploadFile(file.file, projectId.value)
    message.success('文件已导入并索引')
    showIngest.value = false
    loadDocs()
  } catch (e) {
    message.error(e.message || '上传失败')
  }
}

async function removeDoc(row) {
  const ok = await window.confirm(`确认删除「${row.title}」？`)
  if (!ok) return
  try {
    await knowledgeAPI.deleteDoc(row.id)
    message.success('已删除')
    loadDocs()
  } catch (e) {
    message.error(e.message || '删除失败')
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0 0 4px 0; }
</style>
