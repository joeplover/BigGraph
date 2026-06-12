<template>
  <div class="message-input-wrapper">
    <div class="input-container">
      <div class="mode-indicator" v-if="chatStore.ragMode">
        <el-tag size="small" type="success" effect="light" closable @close="chatStore.toggleRagMode()">
          RAG 模式 {{ chatStore.kbId ? `- ${chatStore.kbId}` : '(未选择知识库)' }}
        </el-tag>
      </div>
      <div class="input-area">
        <el-input
          v-model="text"
          type="textarea"
          :rows="1"
          :autosize="{ minRows: 1, maxRows: 5 }"
          placeholder="输入消息..."
          class="chat-input"
          @keydown.enter.prevent="handleSend"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="chatStore.loading"
          class="send-btn"
          @click="handleSend"
          circle
        />
      </div>
      <div class="input-footer">
        <span class="hint">Enter 发送，Shift+Enter 换行</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Promotion } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const text = ref('')

function handleSend(e) {
  if (e && e.shiftKey) return
  if (!text.value.trim() || chatStore.loading) return

  chatStore.sendMessage(text.value.trim())
  text.value = ''
}
</script>

<style scoped>
.message-input-wrapper {
  border-top: 1px solid var(--border-color, #e5e5e5);
  padding: 16px 60px 24px;
  background: var(--bg-primary, #fff);
}

.input-container {
  max-width: 800px;
  margin: 0 auto;
}

.mode-indicator {
  margin-bottom: 8px;
}

.input-area {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.chat-input :deep(.el-textarea__inner) {
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  border: 1px solid var(--border-color, #e5e5e5);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.chat-input :deep(.el-textarea__inner:focus) {
  border-color: var(--accent-color, #10a37f);
  box-shadow: 0 2px 12px rgba(16, 163, 127, 0.1);
}

.send-btn {
  flex-shrink: 0;
  margin-bottom: 2px;
}

.input-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

.hint {
  font-size: 12px;
  color: var(--text-muted, #a0a0a0);
}
</style>