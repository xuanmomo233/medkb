import { EmptyState } from '@/ui'

export default function Placeholder({ name }: { name: string }) {
  return <EmptyState icon="🚧" text={`「${name}」开发中`} />
}
