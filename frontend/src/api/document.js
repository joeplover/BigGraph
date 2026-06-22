import request from './request'

export function uploadFile(kbId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/api/upload/${kbId}`, formData)
}

export function getJobStatus(jobId) {
  return request.get(`/api/jobs/${jobId}`)
}

export function getDocument(docId) {
  return request.get(`/api/documents/${docId}`)
}

export function searchDocuments(kbId, query, limit = 10) {
  return request.get(`/api/search/${kbId}`, {
    params: { query, limit },
  })
}

export function deleteDocument(docId) {
  return request.delete(`/api/documents/${docId}`)
}
