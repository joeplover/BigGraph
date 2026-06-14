<template>
  <div class="members-page">
    <div class="page-header">
      <el-button text @click="goBack" class="back-btn">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <h2>成员审核</h2>
    </div>

    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="kbList.length === 0" class="empty-wrap">
      <el-empty description="暂无知识库，或您不是任何知识库的创建者" />
    </div>

    <div v-else class="kb-list">
      <div v-for="kb in kbList" :key="kb.id" class="kb-card">
        <div class="kb-header" @click="toggleKb(kb.id)">
          <div class="kb-info">
            <span class="kb-name">{{ kb.name }}</span>
            <el-tag v-if="kb.pendingCount > 0" size="small" type="warning">
              {{ kb.pendingCount }} 个待审批
            </el-tag>
            <el-tag v-else size="small" type="info">无待审批</el-tag>
          </div>
          <el-icon :class="{ expanded: expandedKb === kb.id }">
            <ArrowDown />
          </el-icon>
        </div>

        <div v-if="expandedKb === kb.id" class="kb-members">
          <div v-if="memberLoading[kb.id]" class="member-loading">
            <el-skeleton :rows="2" animated />
          </div>
          <div v-else-if="!memberMap[kb.id] || memberMap[kb.id].length === 0" class="member-empty">
            暂无成员记录
          </div>
          <div v-else v-for="m in memberMap[kb.id]" :key="m.id" class="member-item">
            <div class="member-info">
              <el-avatar :size="32" class="member-avatar">
                {{ (m.display_name || '?').charAt(0).toUpperCase() }}
              </el-avatar>
              <div class="member-detail">
                <span class="member-name">{{ m.display_name }}</span>
                <span class="member-id">ID: {{ m.user_id.slice(0, 8) }}...</span>
              </div>
            </div>
            <div class="member-status">
              <el-tag v-if="m.status === 'approved'" type="success" size="small">已通过</el-tag>
              <el-tag v-else-if="m.status === 'rejected'" type="danger" size="small">已拒绝</el-tag>
              <div v-else class="action-btns">
                <el-button size="small" type="success" :loading="approving[m.id]" @click="handleApprove(kb.id, m.id)">
                  批准
                </el-button>
                <el-button size="small" type="danger" :loading="rejecting[m.id]" @click="handleReject(kb.id, m.id)">
                  拒绝
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { getMembers, approveMember, rejectMember } from '@/api/knowledgeBase'

const router = useRouter()
const chatStore = useChatStore()

const loading = ref(true)
const expandedKb = ref(null)
const approving = ref({})
const rejecting = ref({})
const memberMap = ref({})       // { kbId: [member, ...] }
const memberLoading = ref({})   // { kbId: true/false }

// 只用 computed 来过滤出 owner 的知识库，不存可变状态
const kbList = computed(() => {
  return (chatStore.kbs || []).filter(kb => kb.is_owner).map(kb => ({
    ...kb,
    pendingCount: (memberMap.value[kb.id] || []).filter(m => m.status === 'pending').length,
  }))
})

function goBack() {
  router.push('/chat')
}

async function toggleKb(kbId) {
  if (expandedKb.value === kbId) {
    expandedKb.value = null
    return
  }
  expandedKb.value = kbId

  // 如果还没加载过成员，加载
  if (!memberMap.value[kbId]) {
    memberLoading.value[kbId] = true
    try {
      const res = await getMembers(kbId)
      memberMap.value[kbId] = (res.members || []).map(m => ({
        ...m,
        display_name: m.display_name || m.user_id.slice(0, 8),
      }))
    } catch {
      ElMessage.error('加载成员列表失败')
      memberMap.value[kbId] = []
    } finally {
      memberLoading.value[kbId] = false
    }
  }
}

async function doAction(action, kbId, memberId) {
  const loadingMap = action === 'approve' ? approving : rejecting
  loadingMap.value[memberId] = true
  try {
    if (action === 'approve') {
      await approveMember(kbId, memberId)
      ElMessage.success('已批准')
    } else {
      await rejectMember(kbId, memberId)
      ElMessage.success('已拒绝')
    }
    // 刷新成员列表
    const res = await getMembers(kbId)
    memberMap.value[kbId] = (res.members || []).map(m => ({
      ...m,
      display_name: m.display_name || m.user_id.slice(0, 8),
    }))
  } catch {
    // handled in interceptor
  } finally {
    loadingMap.value[memberId] = false
  }
}

function handleApprove(kbId, memberId) {
  doAction('approve', kbId, memberId)
}

function handleReject(kbId, memberId) {
  doAction('reject', kbId, memberId)
}

onMounted(() => {
  // 确保知识库列表已加载
  if (chatStore.kbs.length === 0) {
    chatStore.fetchMyKbs().finally(() => { loading.value = false })
  } else {
    loading.value = false
  }
})
</script>

<style scoped>
.members-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px;
  min-height: 100vh;
  background: var(--bg-primary, #fff);
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #1f1f1f);
}

.back-btn {
  color: var(--text-secondary, #6b6b6b);
}

.loading-wrap, .empty-wrap {
  padding: 60px 0;
}

.kb-card {
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 10px;
  margin-bottom: 12px;
  overflow: hidden;
}

.kb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.kb-header:hover {
  background: var(--bg-hover, #f5f5f5);
}

.kb-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary, #1f1f1f);
}

.kb-members {
  border-top: 1px solid var(--border-color, #e5e5e5);
  padding: 8px 0;
}

.member-loading, .member-empty {
  padding: 20px 16px;
  text-align: center;
  color: var(--text-muted, #a0a0a0);
  font-size: 13px;
}

.member-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  transition: background 0.2s;
}

.member-item:hover {
  background: var(--bg-hover, #f5f5f5);
}

.member-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.member-avatar {
  background: var(--accent-color, #10a37f);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.member-detail {
  display: flex;
  flex-direction: column;
}

.member-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #1f1f1f);
}

.member-id {
  font-size: 12px;
  color: var(--text-muted, #a0a0a0);
}

.member-status {
  flex-shrink: 0;
}

.action-btns {
  display: flex;
  gap: 6px;
}
</style>