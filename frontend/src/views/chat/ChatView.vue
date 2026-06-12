<template>
  <div class="chat-layout">
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
import { ref, onMounted } from 'vue'
import Sidebar from './Sidebar.vue'
import MessageList from './MessageList.vue'
import MessageInput from './MessageInput.vue'
import ChatHeader from './ChatHeader.vue'
import SettingsDrawer from './SettingsDrawer.vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const showSettings = ref(false)

onMounted(() => {
  chatStore.fetchMyKbs()
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: var(--bg-primary, #fff);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>