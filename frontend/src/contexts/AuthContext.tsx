import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { User, LoginData, RegisterData } from '../types'
import { authApi } from '../services/authApi'
import toast from 'react-hot-toast'

interface AuthContextType {
  user: User | null
  token: string | null
  loading: boolean
  login: (data: LoginData) => Promise<void>
  register: (data: RegisterData) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  isAuthenticated: boolean
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('access_token')
      const savedUser = localStorage.getItem('user')
      
      if (storedToken && savedUser) {
        try {
          // Validate token with server
          await authApi.validateToken()
          setToken(storedToken)
          setUser(JSON.parse(savedUser))
        } catch (error) {
          // Token is invalid, clear local storage
          localStorage.removeItem('access_token')
          localStorage.removeItem('user')
          setToken(null)
        }
      }
      setLoading(false)
    }

    initializeAuth()
  }, [])

  const login = async (data: LoginData) => {
    try {
      const response = await authApi.login(data)
      localStorage.setItem('access_token', response.access_token)
      setToken(response.access_token)
      
      // Get user info
      const user = await authApi.getMe()
      setUser(user)
      localStorage.setItem('user', JSON.stringify(user))
      
      toast.success('ログインしました')
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  }

  const register = async (data: RegisterData) => {
    try {
      await authApi.register(data)
      toast.success('アカウントを作成しました。ログインしてください。')
    } catch (error) {
      console.error('Registration failed:', error)
      throw error
    }
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setToken(null)
    setUser(null)
    toast.success('ログアウトしました')
  }

  const refreshUser = async () => {
    try {
      if (token) {
        const user = await authApi.getMe()
        setUser(user)
        localStorage.setItem('user', JSON.stringify(user))
      }
    } catch (error) {
      console.error('Failed to refresh user:', error)
      // Token might be invalid, logout
      logout()
    }
  }

  const value = {
    user,
    token,
    loading,
    login,
    register,
    logout,
    refreshUser,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin === true,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}