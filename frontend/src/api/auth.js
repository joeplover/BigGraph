import request from './request'

export function sendCode(email) {
  return request.post('/auth/send-code', { email })
}

export function register(data) {
  return request.post('/auth/register', data)
}

export function login(data) {
  return request.post('/auth/login', data)
}

export function refreshToken(refresh_token) {
  return request.post('/auth/refresh', {}, {
    headers: { 'X-Refresh-Token': refresh_token },
  })
}

export function getUserInfo() {
  return request.get('/auth/me')
}

export function logout() {
  return request.post('/auth/logout')
}