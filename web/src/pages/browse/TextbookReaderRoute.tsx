import { lazy, Suspense } from 'react'
import { Spinner } from '@/ui'

const TextbookReaderPage = lazy(() => import('./TextbookReaderPage'))

export default function TextbookReaderRoute() {
  return <Suspense fallback={<Spinner />}><TextbookReaderPage /></Suspense>
}
