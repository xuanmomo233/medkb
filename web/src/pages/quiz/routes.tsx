import type { RouteObject } from 'react-router-dom'
import QuizHome from './QuizHome'
import QuizRun from './run/QuizRun'
import QuizPool from './QuizPool'
import WrongBook from './WrongBook'
import Exams from './Exams'
import Report from './Report'

const routes: RouteObject[] = [
  { path: 'quiz', element: <QuizHome /> },
  { path: 'quiz/run', element: <QuizRun /> },
  { path: 'quiz/pool', element: <QuizPool /> },
  { path: 'quiz/wrongbook', element: <WrongBook /> },
  { path: 'quiz/exams', element: <Exams /> },
  { path: 'quiz/report', element: <Report /> },
]
export default routes
