import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { searchDocuments } from '@/api/document'
import { getMyKnowledgeBases } from '@/api/knowledgeBase'
import request from '@/api/request'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSessionId = ref(null)
  const messages = ref([])
  const ragMode = ref(false)
  const kbId = ref('')
  const kbs = ref([])
  const loading = ref(false)

  const currentSession = computed(() =>
    sessions.value.find((s) => s.id === currentSessionId.value)
  )

  // ================================================================
  //  初始化：从后端加载会话列表和历史
  // ================================================================

  async function loadFromBackend() {
    try {
      const res = await request.get('/api/chat/sessions')
      sessions.value = (res.sessions || []).map(s => ({
        id: s.id,
        title: s.title || '新会话',
        createdAt: s.created_at || new Date().toISOString(),
      }))

      // 恢复上次的 session
      const saved = localStorage.getItem('chat_session_id')
      if (saved && sessions.value.find(s => s.id === saved)) {
        currentSessionId.value = saved
        await loadHistory()
      } else if (sessions.value.length > 0) {
        // 没有保存的 session 就选第一个
        currentSessionId.value = sessions.value[0].id
        localStorage.setItem('chat_session_id', sessions.value[0].id)
        await loadHistory()
      }
    } catch {
      // 首次使用，没有会话也正常
    }
  }

  async function loadHistory() {
    if (!currentSessionId.value) {
      messages.value = []
      return
    }
    try {
      const res = await request.get(`/api/chat/history/${currentSessionId.value}`)
      if (res && res.messages) {
        messages.value = res.messages.map(m => ({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp || new Date().toISOString(),
        }))
      } else {
        messages.value = []
      }
    } catch {
      messages.value = []
    }
  }

  // ================================================================
  //  会话管理
  // ================================================================

  async function newSession() {
    try {
      const session = await request.post('/api/chat/sessions')
      const item = {
        id: session.id,
        title: session.title || '新会话',
        createdAt: session.created_at || new Date().toISOString(),
      }
      sessions.value.unshift(item)
      currentSessionId.value = item.id
      localStorage.setItem('chat_session_id', item.id)
      messages.value = []
    } catch {
      // 离线容错
      const id = Date.now().toString()
      const item = { id, title: '新会话', createdAt: new Date().toISOString() }
      sessions.value.unshift(item)
      currentSessionId.value = id
      localStorage.setItem('chat_session_id', id)
      messages.value = []
    }
  }

  async function deleteSession(id) {
    // 先删后端
    try {
      await request.delete(`/api/chat/history/${id}`)
    } catch { /* ignore */ }

    const idx = sessions.value.findIndex((s) => s.id === id)
    if (idx !== -1) sessions.value.splice(idx, 1)

    if (currentSessionId.value === id) {
      if (sessions.value.length > 0) {
        currentSessionId.value = sessions.value[0].id
        localStorage.setItem('chat_session_id', sessions.value[0].id)
        await loadHistory()
      } else {
        currentSessionId.value = null
        localStorage.removeItem('chat_session_id')
        messages.value = []
      }
    }
  }

  async function selectSession(id) {
    currentSessionId.value = id
    localStorage.setItem('chat_session_id', id)
    messages.value = []
    await loadHistory()
  }

  // ================================================================
  //  发消息
  // ================================================================

  async function sendMessage(text) {
    if (!text.trim()) return

    // 没有 session 时自动创建
    if (!currentSessionId.value) {
      await newSession()
    }

    // 添加用户消息
    const userMsg = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    loading.value = true

    try {
      let responseText = ''
      let thinking = ''
      let chunksData = []

      if (ragMode.value && kbId.value) {
        // RAG 模式：先搜索知识库
        const searchRes = await searchDocuments(kbId.value, text, 5)
        const chunks = searchRes.results || []

        if (chunks.length > 0) {
          // 折叠时显示来源摘要
          const seen = new Set()
          thinking = chunks.map(c => {
            const name = c.file_name || '未知文档'
            if (seen.has(name)) return ''
            seen.add(name)
            return `[${name}]`
          }).filter(Boolean).join(' ')

          chunksData = chunks.map(c => c.content || '')

          // 调用 LLM 回答问题
          const context = chunks.map((c) => c.content).join('\n\n')
          const res = await request.post('/api/chat', {
            message: text,
            session_id: currentSessionId.value,
            context: context,
          })
          responseText = res.response || res.message || '抱歉，我暂时无法回答。'
        } else {
          responseText = '⚠️ 知识库中未找到与问题相关的信息。'
        }
      } else if (ragMode.value && !kbId.value) {
        responseText = '⚠️ 请先选择一个知识库再使用 RAG 模式。'
      } else {
        // 普通模式
        const res = await request.post('/api/chat', {
          message: text,
          session_id: currentSessionId.value,
        })
        responseText = res.response || res.message || '抱歉，我暂时无法回答。'
      }

      messages.value.push({
        role: 'assistant',
        content: responseText,
        thinking: thinking || '',
        chunksData: chunksData,
        timestamp: new Date().toISOString(),
      })

      // 更新会话标题（第一条消息，同步到后端）
      const session = sessions.value.find((s) => s.id === currentSessionId.value)
      if (session && session.title === '新会话') {
        const newTitle = text.slice(0, 30) + (text.length > 30 ? '...' : '')
        session.title = newTitle
        try {
          await request.patch(`/api/chat/sessions/${currentSessionId.value}`, { title: newTitle })
        } catch { /* 不重要 */ }
      }
    } catch (e) {
      messages.value.push({
        role: 'assistant',
        content: '❌ 请求失败，请稍后重试。',
        timestamp: new Date().toISOString(),
      })
    } finally {
      loading.value = false
    }
  }

  async function fetchMyKbs() {
    try {
      const res = await getMyKnowledgeBases()
      kbs.value = res || []
    } catch {
      kbs.value = []
    }
  }

  function toggleRagMode() {
    ragMode.value = !ragMode.value
  }

  function setKbId(id) {
    kbId.value = id
  }

  // ================================================================
  //  启动：加载数据
  // ================================================================
  loadFromBackend()

  return {
    sessions,
    currentSessionId,
    messages,
    ragMode,
    kbId,
    kbs,
    loading,
    currentSession,
    newSession,
    deleteSession,
    selectSession,
    sendMessage,
    fetchMyKbs,
    toggleRagMode,
    setKbId,
  }
})
