<template>
  <el-drawer
    v-model="visible"
    :size="360"
    title="设置"
    direction="rtl"
  >
    <div class="settings-content">
      <!-- 用户信息 -->
      <div class="section">
        <h3 class="section-title">用户信息</h3>
        <div class="user-card">
          <el-avatar :size="48" class="user-avatar-big">
            {{ userInitial }}
          </el-avatar>
          <div class="user-detail">
            <p class="user-name">{{ displayName }}</p>
            <p class="user-id">ID: {{ userId }}</p>
          </div>
        </div>
        <el-button class="logout-btn" @click="handleLogout">
          退出登录
        </el-button>
      </div>

      <el-divider />

      <!-- RAG 模式 -->
      <div class="section">
        <h3 class="section-title">聊天模式</h3>
        <div class="mode-switch">
          <div class="mode-info">
          <el-tag v-if="chatStore.ragMode" type="success" closable @close="chatStore.toggleRagMode()" size="small" effect="plain">RAG 模式</el-tag>
          <span v-else class="mode-label">RAG 模式</span>
            <span class="mode-desc">开启后将基于知识库内容回答</span>
          </div>
          <el-switch
            :model-value="chatStore.ragMode"
            @change="onRagModeChange"
          />
        </div>

        <!-- PPT Agent 模式 -->
        <div class="mode-switch" style="margin-top: 12px;">
          <div class="mode-info">
          <el-tag v-if="chatStore.pptMode" type="warning" closable @close="chatStore.togglePptMode()" size="small" effect="plain">PPT Agent 模式</el-tag>
          <span v-else class="mode-label">PPT Agent 模式</span>
            <span class="mode-desc">开启后将进入专业的 PPT 制作助手模式</span>
          </div>
          <el-switch
            :model-value="chatStore.pptMode"
            @change="onPptModeChange"
          />
        </div>

        <!-- PPT Agent 提示 -->
        <div v-if="chatStore.pptMode" class="ppt-mode-hint">
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            title="PPT Agent 模式下对话将用于制作 PPT，而非普通问答"
          />
        </div>
      </div>

      <!-- 选择知识库 -->
      <div class="section" v-if="chatStore.ragMode">
        <h3 class="section-title">选择知识库</h3>
        <el-select
          v-model="selectedKb"
          placeholder="选择知识库"
          style="width: 100%"
          @change="chatStore.setKbId"
        >
          <el-option
            v-for="kb in chatStore.kbs"
            :key="kb.id"
            :label="kb.name"
            :value="kb.id"
          />
        </el-select>
        <p class="no-kb-hint" v-if="chatStore.kbs.length === 0">
          暂无知识库，请先创建或加入知识库
        </p>
      </div>

      <el-divider />

      <!-- 知识库管理 -->
      <div class="section">
        <div class="section-header">
          <h3 class="section-title">知识库管理</h3>
        </div>
        <el-button type="primary" size="small" class="action-btn" @click="showCreateKb = true">
          创建知识库
        </el-button>
        <el-button size="small" class="action-btn" @click="showJoinKb = true">
          加入知识库
        </el-button>
      </div>

      <!-- 我的知识库列表 -->
      <div class="section">
        <h3 class="section-title">我的知识库</h3>
        <div v-for="kb in chatStore.kbs" :key="kb.id" class="kb-item">
          <div class="kb-info">
            <span class="kb-name">{{ kb.name }}</span>
            <span class="kb-id">{{ kb.id.slice(0, 8) }}...</span>
          </div>
          <div class="kb-actions">
            <el-button text size="small" @click="handleShare(kb.id)">
              分享
            </el-button>
            <el-button text size="small" type="primary" @click="openUpload(kb)">
              上传
            </el-button>
          </div>
        </div>
        <p v-if="chatStore.kbs.length === 0" class="empty-text">暂无知识库</p>
      </div>
    </div>

    <!-- 创建知识库对话框 -->
    <el-dialog v-model="showCreateKb" title="创建知识库" width="400px" append-to-body>
      <el-form :model="createForm">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.desc" type="textarea" :rows="3" placeholder="描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateKb = false">取消</el-button>
        <el-button type="primary" :loading="creatingKb" @click="handleCreateKb">创建</el-button>
      </template>
    </el-dialog>

    <!-- 加入知识库对话框 -->
    <el-dialog v-model="showJoinKb" title="加入知识库" width="400px" append-to-body>
      <el-form>
        <el-form-item label="分享码">
          <el-input v-model="shareCode" placeholder="输入分享码，如 KB-xxxx" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showJoinKb = false">取消</el-button>
        <el-button type="primary" :loading="joiningKb" @click="handleJoinKb">加入</el-button>
      </template>
    </el-dialog>

    <!-- 分享码显示 -->
    <el-dialog v-model="showShareCode" title="分享码" width="400px" append-to-body>
      <p class="share-code-display">{{ shareCodeResult }}</p>
      <p class="share-hint">将此分享码发送给其他人，他们即可申请加入此知识库</p>
      <template #footer>
        <el-button @click="showShareCode = false">关闭</el-button>
        <el-button type="primary" @click="copyShareCode">复制</el-button>
      </template>
    </el-dialog>

    <!-- 上传文档对话框 -->
    <el-dialog
      v-model="showUpload"
      title="上传文档"
      width="420px"
      append-to-body
      :close-on-click-modal="uploadDone"
    >
      <template v-if="!uploading">
        <p class="upload-target">上传到：<strong>{{ uploadKb?.name }}</strong></p>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :show-file-list="true"
          :limit="1"
          :on-change="onFileChange"
        >
          <el-button type="primary" :icon="Upload">选择文件</el-button>
          <template #tip>
            <p class="upload-tip">支持 PDF、Word、Markdown、TXT 等格式</p>
          </template>
        </el-upload>
      </template>
      <template v-else>
        <div class="upload-progress">
          <el-progress :percentage="uploadProgress" :status="uploadStatus" />
          <p class="upload-status-text">{{ uploadStatusText }}</p>
        </div>
      </template>
      <template #footer>
        <el-button @click="closeUpload">
          {{ uploadDone ? '关闭' : '取消' }}
        </el-button>
        <el-button
          v-if="!uploadDone"
          type="primary"
          :loading="uploading"
          :disabled="!selectedFile || uploading"
          @click="handleUpload"
        >
          {{ uploading ? '上传中...' : '开始上传' }}
        </el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { createKnowledgeBase, shareKnowledgeBase, joinKnowledgeBase } from '@/api/knowledgeBase'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])

function onPptModeChange() {
  chatStore.togglePptMode()
}

function onRagModeChange() {
  chatStore.toggleRagMode()
}
const chatStore = useChatStore()
const authStore = useAuthStore()
const router = useRouter()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const displayName = computed(() => authStore.userInfo?.display_name || '用户')
const userId = computed(() => authStore.userInfo?.user_id?.slice(0, 8) || '')
const userInitial = computed(() => displayName.value.charAt(0).toUpperCase())

const selectedKb = ref('')

// 知识库创建
const showCreateKb = ref(false)
const creatingKb = ref(false)
const createForm = ref({ name: '', desc: '' })

// 加入知识库
const showJoinKb = ref(false)
const joiningKb = ref(false)
const shareCode = ref('')

// 分享码
const showShareCode = ref(false)
const shareCodeResult = ref('')

// 上传文档
const showUpload = ref(false)
const uploadKb = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const uploadDone = ref(false)
const uploadProgress = ref(0)
const uploadStatus = ref('')  // '' | 'success' | 'exception'
const uploadStatusText = ref('')

function openUpload(kb) {
  uploadKb.value = kb
  selectedFile.value = null
  uploading.value = false
  uploadDone.value = false
  uploadProgress.value = 0
  uploadStatus.value = ''
  uploadStatusText.value = ''
  showUpload.value = true
}

function onFileChange(file) {
  selectedFile.value = file.raw || file
}

function closeUpload() {
  showUpload.value = false
  uploading.value = false
  uploadDone.value = false
}

function finishUpload(success, msg) {
  uploading.value = false
  uploadDone.value = true
  if (success) {
    uploadStatus.value = 'success'
    uploadProgress.value = 100
    ElMessage.success(msg)
  } else {
    uploadStatus.value = 'exception'
    ElMessage.error(msg)
  }
  uploadStatusText.value = msg
}

async function handleUpload() {
  if (!selectedFile.value || !uploadKb.value) return
  uploading.value = true
  uploadDone.value = false
  uploadProgress.value = 10
  uploadStatusText.value = '正在上传...'

  try {
    const { uploadFile, getJobStatus } = await import('@/api/document')
    const res = await uploadFile(uploadKb.value.id, selectedFile.value)
    uploadProgress.value = 50
    uploadStatusText.value = '上传成功，后台处理中...'

    // 如果有 job_id，轮询处理进度
    if (res.job_id) {
      let cancelled = false
      const poll = async () => {
        if (cancelled) return
        try {
          const job = await getJobStatus(res.job_id)
          uploadProgress.value = job.progress || 50
          if (job.status === 'completed') {
            finishUpload(true, '文档处理完成')
            return
          }
          if (job.status === 'failed') {
            finishUpload(false, job.error_message || '文档处理失败')
            return
          }
          // 继续轮询
          setTimeout(poll, 2000)
        } catch {
          finishUpload(true, '上传完成，可在知识库中查看')
        }
      }
      setTimeout(poll, 2000)
    } else {
      finishUpload(true, '上传成功')
    }
  } catch (e) {
    finishUpload(false, '上传失败，请重试')
  }
}

async function handleCreateKb() {
  if (!createForm.value.name) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  creatingKb.value = true
  try {
    await createKnowledgeBase(createForm.value.name, createForm.value.desc)
    ElMessage.success('创建成功')
    showCreateKb.value = false
    createForm.value = { name: '', desc: '' }
    await chatStore.fetchMyKbs()
  } finally {
    creatingKb.value = false
  }
}

async function handleShare(kbId) {
  try {
    const res = await shareKnowledgeBase(kbId)
    shareCodeResult.value = res.share_code
    showShareCode.value = true
  } catch {
    // handled in interceptor
  }
}

function copyShareCode() {
  navigator.clipboard.writeText(shareCodeResult.value)
  ElMessage.success('已复制分享码')
}

async function handleJoinKb() {
  if (!shareCode.value) {
    ElMessage.warning('请输入分享码')
    return
  }
  joiningKb.value = true
  try {
    const res = await joinKnowledgeBase(shareCode.value.trim())
    ElMessage.success(res.message || '已发送加入申请')
    showJoinKb.value = false
    shareCode.value = ''
    await chatStore.fetchMyKbs()
  } finally {
    joiningKb.value = false
  }
}

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.settings-content {
  padding: 0 8px;
}

.section {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1f1f1f);
  margin-bottom: 12px;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.user-avatar-big {
  background: var(--accent-color, #10a37f);
  color: #fff;
  font-weight: 600;
}

.user-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary, #1f1f1f);
}

.user-id {
  font-size: 12px;
  color: var(--text-muted, #a0a0a0);
}

.logout-btn {
  width: 100%;
}

.mode-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mode-label {
  font-size: 14px;
  color: var(--text-primary, #1f1f1f);
}

.mode-desc {
  display: block;
  font-size: 12px;
  color: var(--text-muted, #a0a0a0);
  margin-top: 2px;
}

.no-kb-hint, .empty-text {
  font-size: 13px;
  color: var(--text-muted, #a0a0a0);
  margin-top: 8px;
}

.action-btn {
  margin-right: 8px;
  margin-bottom: 8px;
}

.kb-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color, #e5e5e5);
}

.kb-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.kb-name {
  font-size: 14px;
  color: var(--text-primary, #1f1f1f);
  display: block;
}

.kb-id {
  font-size: 12px;
  color: var(--text-muted, #a0a0a0);
}

.share-code-display {
  font-size: 18px;
  font-weight: 600;
  text-align: center;
  padding: 20px;
  color: var(--accent-color, #10a37f);
  background: var(--bg-secondary, #f7f7f8);
  border-radius: 8px;
  letter-spacing: 1px;
}

.share-hint {
  font-size: 13px;
  color: var(--text-muted, #a0a0a0);
  text-align: center;
  margin-top: 8px;
}

.upload-target {
  font-size: 14px;
  color: var(--text-primary, #1f1f1f);
  margin-bottom: 16px;
}

.upload-tip {
  font-size: 12px;
  color: var(--text-muted, #a0a0a0);
  margin-top: 4px;
}

.upload-progress {
  padding: 20px 0;
  text-align: center;
}

.upload-status-text {
  font-size: 14px;
  color: var(--text-secondary, #6b6b6b);
  margin-top: 12px;
}

.ppt-mode-hint {
  margin-top: 12px;
}
</style>