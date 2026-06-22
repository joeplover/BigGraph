import request from './request'

// Get visible knowledge bases for the current user.
export function getMyKnowledgeBases() {
  return request.get('/api/knowledge_bases/')
}

export function createKnowledgeBase(name, description = '') {
  return request.post('/api/knowledge_bases/', null, {
    params: { name, description },
  })
}

export function getKnowledgeBase(kbId) {
  return request.get(`/api/knowledge_bases/${kbId}`)
}

export function shareKnowledgeBase(kbId) {
  return request.post(`/api/knowledge_bases/${kbId}/share`)
}

export function joinKnowledgeBase(shareCode) {
  return request.post(`/api/knowledge_bases/join/${shareCode}`)
}

export function approveMember(kbId, memberId) {
  return request.post(`/api/knowledge_bases/${kbId}/members/${memberId}/approve`)
}

export function rejectMember(kbId, memberId) {
  return request.post(`/api/knowledge_bases/${kbId}/members/${memberId}/reject`)
}

export function removeMember(kbId, memberId) {
  return request.delete(`/api/knowledge_bases/${kbId}/members/${memberId}`)
}

export function getMembers(kbId) {
  return request.get(`/api/knowledge_bases/${kbId}/members`)
}

export function deleteKnowledgeBase(kbId) {
  return request.delete(`/api/knowledge_bases/${kbId}`)
}
