import api from './api'
import { LoginData, RegisterData, AuthResponse, User } from '../types'

export const authApi = {
  login: async (data: LoginData): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/login', data)
    return response.data
  },

  register: async (data: RegisterData): Promise<User> => {
    const response = await api.post<User>('/auth/register', data)
    return response.data
  },

  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me')
    return response.data
  },

  validateToken: async (): Promise<{ valid: boolean; user_id: string }> => {
    const response = await api.get('/auth/validate-token')
    return response.data
  },

  createInvite: async (email: string): Promise<{ message: string; invitation_token: string; registration_url: string }> => {
    const response = await api.post('/auth/invite', { email })
    return response.data
  },
}