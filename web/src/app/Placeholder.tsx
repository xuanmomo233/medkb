import { EmptyState } from '@/ui'

export default function Placeholder({ name }: { name: string }) {
  return <EmptyState icon="settings" text={`「${name}」开发中`} />
}
