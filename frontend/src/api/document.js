import request from './request'

export function uploadFile(kbId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/upload/${kbId}`, formData)
}

export function getJobStatus(jobId) {
  return request.get(`/jobs/${jobId}`)
}

export function getDocument(docId) {
  return request.get(`/documents/${docId}`)
}

export function searchDocuments(kbId, query, limit = 10) {
  return request.get(`/search/${kbId}`, {
    params: { query, limit },
  })
}

export function deleteDocument(docId) {
  return request.delete(`/documents/${docId}`)
}