<template>
  <div class="chat-header">
    <div class="header-left">
      <h2 class="title">{{ sessionTitle }}</h2>
    </div>
    <div class="header-right">
      <el-tag
        v-if="chatStore.ragMode"
        type="success"
        effect="light"
        size="small"
        closable
        @close="turnOffRag"
      >
        RAG 模式
      </el-tag>
      <el-tag
        v-if="chatStore.pptMode"
        type="warning"
        effect="light"
        size="small"
        closable
        @close="turnOffPpt"
      >
        PPT 模式
      </el-tag>
      <el-button text @click="emit('openSettings')">
        <el-icon><Setting /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Setting } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'

const emit = defineEmits(['openSettings'])
const chatStore = useChatStore()

const sessionTitle = computed(() => {
  if (chatStore.currentSession) {
    return chatStore.currentSession.title
  }
  return '新对话'
})

function turnOffRag() {
  chatStore.ragMode = false
}

function turnOffPpt() {
  chatStore.pptMode = false
}
</script>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height, 48px);
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color, #e5e5e5);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #1f1f1f);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>