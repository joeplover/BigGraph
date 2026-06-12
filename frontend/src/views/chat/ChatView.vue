<template>
  <div class="chat-layout" :class="{ 'ppt-mode-active': pptBgActive, 'rag-mode-active': ragBgActive }">
    <Sidebar @openSettings="showSettings = true" />
    <div class="main-content">
      <ChatHeader @openSettings="showSettings = true" />
      <MessageList />
      <MessageInput />
    </div>
    <SettingsDrawer v-model="showSettings" />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import Sidebar from './Sidebar.vue'
import MessageList from './MessageList.vue'
import MessageInput from './MessageInput.vue'
import ChatHeader from './ChatHeader.vue'
import SettingsDrawer from './SettingsDrawer.vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const showSettings = ref(false)
const pptBgActive = ref(false)
const ragBgActive = ref(false)

onMounted(() => {
  chatStore.fetchMyKbs()
  // 初始化同步
  pptBgActive.value = chatStore.pptMode
  ragBgActive.value = chatStore.ragMode
})

// 直接监听 store 状态，不管从哪里修改都会同步
watch(() => chatStore.pptMode, (val) => {
  ragBgActive.value = false
  pptBgActive.value = val
})

watch(() => chatStore.ragMode, (val) => {
  pptBgActive.value = false
  ragBgActive.value = val
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: var(--bg-primary, #fff);
  transition: background 0.6s ease;
}

/* PPT 模式 — 橙色 */
.chat-layout.ppt-mode-active {
  background: #C25033;
  --bg-sidebar: rgba(255,255,255,0.12);
  --bg-hover: rgba(255,255,255,0.18);
  --border-color: rgba(0,0,0,0.08);
  --text-primary: #1f1f1f;
  --text-secondary: #6b6b6b;
  --text-muted: #a0a0a0;
}

/* RAG 模式 — 蓝色 */
.chat-layout.rag-mode-active {
  background: #3b82f6;
  --bg-sidebar: rgba(255,255,255,0.12);
  --bg-hover: rgba(255,255,255,0.18);
  --border-color: rgba(0,0,0,0.08);
  --text-primary: #1f1f1f;
  --text-secondary: #6b6b6b;
  --text-muted: #a0a0a0;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* 模式激活时，聊天区白色卡片浮在彩色背景上 */
.chat-layout.ppt-mode-active .main-content,
.chat-layout.rag-mode-active .main-content {
  margin: 12px 0 12px 12px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.chat-layout.ppt-mode-active .main-content :deep(.chat-header),
.chat-layout.rag-mode-active .main-content :deep(.chat-header) {
  border-radius: 12px 12px 0 0;
}
</style>
