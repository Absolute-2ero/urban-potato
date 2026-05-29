import client from './client'
import type { User, UserCreate, UserLogin } from '@/types'

export const register = (data: UserCreate) =>
  client.post<User>('/api/auth/register', data).then((r) => r.data)

export const login = (data: UserLogin) =>
  client.post<User>('/api/auth/login', data).then((r) => r.data)

export const logout = () =>
  client.post('/api/auth/logout').then((r) => r.data)

export const getMe = () =>
  client.get<User>('/api/auth/me').then((r) => r.data)

export const deleteAccount = () =>
  client.delete('/api/auth/me')
