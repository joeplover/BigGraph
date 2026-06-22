import request from './request'

// 获取我的知识库
export function getMyKnowledgeBases() {
  // 先获取所有可见的知识库
  return request.get('/api/knowledge_bases/')
}

// 创建知识库
export function createKnowledgeBase(name, description = '') {
  return request.post('/api/knowledge_bases/', null, {
    params: { name, description },
  })
}

// 获取知识库详情
export function getKnowledgeBase(kbId) {
  return request.get(`/api/knowledge_bases/${kbId}`)
}

// 生成分享码
export function shareKnowledgeBase(kbId) {
  return request.post(`/api/knowledge_bases/${kbId}/share`)
}

// 通过分享码加入
export function joinKnowledgeBase(shareCode) {
  return request.post(`/api/knowledge_bases/join/${shareCode}`)
}

// 审批成员
export function approveMember(kbId, memberId) {
  return request.post(`/api/knowledge_bases/${kbId}/members/${memberId}/approve`)
}

// 获取成员列表
export function getMembers(kbId) {
  return request.get(`/api/knowledge_bases/${kbId}/members`)
}

// 删除知识库（仅发布者）
export function deleteKnowledgeBase(kbId) {
  return request.delete(`/api/knowledge_bases/${kbId}`)
}
