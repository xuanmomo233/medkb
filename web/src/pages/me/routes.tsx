import type { RouteObject } from 'react-router-dom'
import MePage from './MePage'
import AdminPage from './AdminPage'
import MyNotesPage from './MyNotesPage'
import SettingsPage from './SettingsPage'

const routes: RouteObject[] = [
  { path: 'me', element: <MePage /> },
  { path: 'me/notes', element: <MyNotesPage /> },
  { path: 'me/settings', element: <SettingsPage /> },
  { path: 'me/admin', element: <AdminPage /> },
]
export default routes
