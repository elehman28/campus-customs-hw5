export interface Toast {
  id: string
  tone: 'ok' | 'info' | 'error'
  title: string
  body?: string
}

export default function Toasts({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.tone}`}>
          <b>{t.title}</b>
          {t.body && <span>{t.body}</span>}
        </div>
      ))}
    </div>
  )
}
