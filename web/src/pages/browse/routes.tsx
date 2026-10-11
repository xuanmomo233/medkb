import type { RouteObject } from 'react-router-dom'
import BrowsePage from './BrowsePage'
import ChapterPage from './ChapterPage'
import SearchPage from './SearchPage'

const routes: RouteObject[] = [
  { path: 'browse', element: <BrowsePage /> },
  { path: 'browse/chapter/:id', element: <ChapterPage /> },
  { path: 'search', element: <SearchPage /> },
]
export default routes
