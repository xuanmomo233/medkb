import { createBrowserRouter, Navigate } from 'react-router-dom'
import { RequireAuth } from './auth'
import Layout from './Layout'
import authRoutes from '@/pages/auth/routes'
import todayRoutes from '@/pages/today/routes'
import browseRoutes from '@/pages/browse/routes'
import cardsRoutes from '@/pages/cards/routes'
import quizRoutes from '@/pages/quiz/routes'
import chatRoutes from '@/pages/chat/routes'
import meRoutes from '@/pages/me/routes'

export const router = createBrowserRouter([
  ...authRoutes,
  {
    path: '/',
    element: <RequireAuth><Layout /></RequireAuth>,
    children: [
      ...todayRoutes, ...browseRoutes, ...cardsRoutes, ...quizRoutes, ...chatRoutes, ...meRoutes,
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
