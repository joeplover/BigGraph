import request from './request'

export function sendCode(email) {
  return request.post('/api/auth/send-code', { email })
}

export function register(data) {
  return request.post('/api/auth/register', data)
}

export function login(data) {
  return request.post('/api/auth/login', data)
}

export function refreshToken(refresh_token) {
  return request.post('/api/auth/refresh', {}, {
    headers: { 'X-Refresh-Token': refresh_token },
  })
}

export function getUserInfo() {
  return request.get('/api/auth/me')
}

export function logout() {
  return request.post('/api/auth/logout')
}
