import type { RouteObject } from 'react-router-dom'
import MePage from './MePage'
import MyNotesPage from './MyNotesPage'
import SettingsPage from './SettingsPage'

const routes: RouteObject[] = [
  { path: 'me', element: <MePage /> },
  { path: 'me/notes', element: <MyNotesPage /> },
  { path: 'me/settings', element: <SettingsPage /> },
]
export default routes
