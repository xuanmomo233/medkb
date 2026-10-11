import type { RouteObject } from 'react-router-dom'
import ChatPage from './ChatPage'

const routes: RouteObject[] = [{ path: 'chat', element: <ChatPage /> }]
export default routes
