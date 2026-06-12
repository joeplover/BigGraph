<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <el-button type="primary" class="new-chat-btn" @click="handleNewChat">
        <el-icon><Plus /></el-icon>
        <span>新对话</span>
      </el-button>
    </div>

    <div class="sidebar-sessions">
      <div
        v-for="session in chatStore.sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === chatStore.currentSessionId }"
        @click="chatStore.selectSession(session.id)"
      >
        <el-icon class="session-icon"><ChatDotSquare /></el-icon>
        <span class="session-title">{{ session.title }}</span>
        <el-button
          class="delete-btn"
          text
          size="small"
          @click.stop="handleDelete(session.id)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="user-info" @click="showSettings">
        <el-avatar :size="32" class="user-avatar">
          {{ userInitial }}
        </el-avatar>
        <span class="username">{{ displayName }}</span>
      </div>
      <el-button text class="settings-btn" @click="showSettings">
        <el-icon><Setting /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, ChatDotSquare, Delete, Setting } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits(['openSettings'])
const chatStore = useChatStore()
const authStore = useAuthStore()
const router = useRouter()

const displayName = computed(() => authStore.userInfo?.display_name || '用户')
const userInitial = computed(() => displayName.value.charAt(0).toUpperCase())

function showSettings() {
  emit('openSettings')
}

function handleNewChat() {
  chatStore.newSession()
}

async function handleDelete(id) {
  try {
    await ElMessageBox.confirm('确定删除此对话？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await chatStore.deleteSession(id)
  } catch {}
}
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width, 260px);
  background: var(--bg-sidebar, #f0f0f0);
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color, #e5e5e5);
  flex-shrink: 0;
}

.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid var(--border-color, #e5e5e5);
}

.new-chat-btn {
  width: 100%;
  justify-content: center;
  gap: 6px;
}

.sidebar-sessions {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  gap: 8px;
  margin-bottom: 2px;
}

.session-item:hover {
  background: var(--bg-hover, #e5e5e5);
}

.session-item.active {
  background: var(--bg-hover, #e5e5e5);
}

.session-icon {
  color: var(--text-secondary, #6b6b6b);
  flex-shrink: 0;
}

.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: var(--text-primary, #1f1f1f);
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border-color, #e5e5e5);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex: 1;
}

.user-avatar {
  background: var(--accent-color, #10a37f);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}

.username {
  font-size: 14px;
  color: var(--text-primary, #1f1f1f);
}

.settings-btn {
  color: var(--text-secondary, #6b6b6b);
}
</style>