import type { RouteObject } from 'react-router-dom'
import BrowsePage from './BrowsePage'
import ChapterPage from './ChapterPage'
import SearchPage from './SearchPage'
import TextbookCatalogPage from './TextbookCatalogPage'
import TextbookReaderRoute from './TextbookReaderRoute'

const routes: RouteObject[] = [
  { path: 'browse', element: <BrowsePage /> },
  { path: 'browse/chapter/:id', element: <ChapterPage /> },
  { path: 'browse/textbooks', element: <TextbookCatalogPage /> },
  { path: 'browse/textbooks/:sourceKey', element: <TextbookReaderRoute /> },
  { path: 'search', element: <SearchPage /> },
]
export default routes
