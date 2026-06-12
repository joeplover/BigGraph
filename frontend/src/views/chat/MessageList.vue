<template>
  <div class="message-list" ref="listRef">
    <div v-if="chatStore.messages.length === 0" class="empty-state">
      <div class="empty-logo">BigGraph</div>
      <p class="empty-subtitle">智能知识库问答平台</p>
      <div v-if="!chatStore.pptMode" class="suggestions">
        <div class="suggestion-item" @click="askSuggestion('你好，介绍一下你自己')">
          <el-icon><ChatLineRound /></el-icon>
          <span>你好，介绍一下你自己</span>
        </div>
        <div class="suggestion-item" @click="askSuggestion('给我讲讲知识库的功能')">
          <el-icon><Document /></el-icon>
          <span>给我讲讲知识库的功能</span>
        </div>
      </div>
      <div v-else class="suggestions">
        <div class="suggestion-item" @click="askSuggestion('帮我做一个关于毕业答辩的 10 页 PPT')">
          <el-icon><ChatLineRound /></el-icon>
          <span>帮我做一个毕业答辩 PPT</span>
        </div>
        <div class="suggestion-item" @click="askSuggestion('帮我做一个项目汇报的 PPT，风格简洁商务')">
          <el-icon><Document /></el-icon>
          <span>帮我做项目汇报 PPT</span>
        </div>
      </div>
    </div>

    <div v-for="(msg, idx) in chatStore.messages" :key="idx" class="message-wrapper" :class="msg.role">
      <div class="message-container">
        <div class="avatar">
          <el-avatar :size="30" v-if="msg.role === 'assistant'" class="ai-avatar">
            <el-icon><Monitor /></el-icon>
          </el-avatar>
          <el-avatar :size="30" v-else class="user-avatar">
            {{ userInitial }}
          </el-avatar>
        </div>
        <div class="message-content">
          <!-- thinking 折叠区（仅 assistant 且有 thinking 时显示） -->
          <div v-if="msg.role === 'assistant' && msg.thinking" class="thinking-section">
            <div class="thinking-header" @click="toggleThinking(idx)">
              <span class="thinking-toggle">{{ expandedThinking[idx] ? '▼' : '▶' }}</span>
              <span class="thinking-label">已检索 {{ msg.thinking.split('\n').length }} 个文档片段</span>
            </div>
            <div v-show="expandedThinking[idx]" class="thinking-body">
              <template v-if="msg.chunksData && msg.chunksData.length">
                <div v-for="(content, ci) in msg.chunksData" :key="ci" class="chunk-text">
                  {{ content }}
                </div>
              </template>
              <template v-else>
                <div class="chunk-text">{{ msg.thinking }}</div>
              </template>
            </div>
          </div>
          <!-- 实际回答 -->
          <div class="message-text">{{ msg.content }}</div>
          <!-- PPT 下载按钮（只在该消息有下载链接时显示） -->
          <div v-if="msg.pptDownloadUrl" class="ppt-download-area">
            <el-button type="primary" size="small" :icon="Download" @click="downloadPpt(msg.pptDownloadUrl)">
              下载 PPT
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="chatStore.loading" class="message-wrapper assistant">
      <div class="message-container">
        <div class="avatar">
          <el-avatar :size="30" class="ai-avatar">
            <el-icon><Monitor /></el-icon>
          </el-avatar>
        </div>
        <div class="message-content">
          <div class="thinking-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>
    </div>

    <div ref="bottomRef"></div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { ChatLineRound, Document, Monitor, Download } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'

const chatStore = useChatStore()
const authStore = useAuthStore()
const listRef = ref(null)
const bottomRef = ref(null)
const expandedThinking = ref({})

const userInitial = computed(() => authStore.userInfo?.display_name?.charAt(0)?.toUpperCase() || 'U')

function askSuggestion(text) {
  chatStore.sendMessage(text)
}

function toggleThinking(idx) {
  expandedThinking.value[idx] = !expandedThinking.value[idx]
}

function downloadPpt(url) {
  if (url) {
    window.open(url, '_blank')
  }
}

// 自动滚动到底部
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    bottomRef.value?.scrollIntoView({ behavior: 'smooth' })
  }
)

watch(
  () => chatStore.loading,
  async () => {
    await nextTick()
    bottomRef.value?.scrollIntoView({ behavior: 'smooth' })
  }
)
</script>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px 20px;
  text-align: center;
}

.empty-logo {
  font-size: 48px;
  font-weight: 700;
  color: var(--accent-color, #10a37f);
  margin-bottom: 8px;
}

.empty-subtitle {
  font-size: 16px;
  color: var(--text-secondary, #6b6b6b);
  margin-bottom: 40px;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 400px;
  width: 100%;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-primary, #1f1f1f);
  font-size: 14px;
}

.suggestion-item:hover {
  background: var(--bg-hover, #e5e5e5);
  border-color: var(--accent-color, #10a37f);
}

.message-wrapper {
  padding: 24px 60px;
}

.message-wrapper.user {
  background: var(--bg-secondary, #f7f7f8);
}

.message-container {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  gap: 16px;
}

.avatar {
  flex-shrink: 0;
}

.ai-avatar {
  background: var(--accent-color, #10a37f);
}

.user-avatar {
  background: #409eff;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-text {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-primary, #1f1f1f);
  white-space: pre-wrap;
  word-break: break-word;
}

.thinking-section {
  margin-bottom: 12px;
  border-left: 3px solid var(--border-color, #e5e5e5);
  padding-left: 12px;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  padding: 4px 0;
  color: var(--text-muted, #a0a0a0);
  font-size: 13px;
  font-style: italic;
}

.thinking-header:hover {
  color: var(--text-secondary, #6b6b6b);
}

.thinking-toggle {
  font-size: 10px;
  flex-shrink: 0;
}

.thinking-label {
  color: inherit;
}

.thinking-body {
  margin-top: 4px;
}

.chunk-text {
  font-size: 13px;
  color: var(--text-secondary, #6b6b6b);
  font-style: italic;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 12px;
}

.chunk-text:last-child {
  margin-bottom: 0;
}

.thinking-dots {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.dot {
  width: 8px;
  height: 8px;
  background: var(--text-muted, #a0a0a0);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.ppt-download-area {
  margin-top: 12px;
}
</style>