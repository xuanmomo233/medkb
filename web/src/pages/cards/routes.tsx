import type { RouteObject } from 'react-router-dom'
import CardRunPage from './CardRunPage'
import CardsPickPage from './CardsPickPage'

const routes: RouteObject[] = [
  { path: 'cards', element: <CardsPickPage /> },
  { path: 'cards/run', element: <CardRunPage /> },
]
export default routes
