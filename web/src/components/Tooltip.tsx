import { useState, useRef, useEffect, type ReactNode } from 'react'

interface TooltipProps {
  children: ReactNode
  content: ReactNode
}

export function Tooltip({ children, content }: TooltipProps) {
  const [show, setShow] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  const triggerRef = useRef<HTMLSpanElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (show && triggerRef.current && tipRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      const tipRect = tipRef.current.getBoundingClientRect()
      let left = rect.left + rect.width / 2 - tipRect.width / 2
      const top = rect.top - tipRect.height - 8

      // Keep within viewport
      if (left < 8) left = 8
      if (left + tipRect.width > window.innerWidth - 8) {
        left = window.innerWidth - tipRect.width - 8
      }

      setPos({ top: top + window.scrollY, left })
    }
  }, [show])

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => { setShow(false); setPos(null) }}
        className="cursor-help"
      >
        {children}
      </span>
      {show && (
        <div
          ref={tipRef}
          className="fixed z-[9999] max-w-sm px-4 py-3 bg-zinc-800 border border-zinc-600 rounded-lg shadow-2xl
                     text-sm text-zinc-200 leading-relaxed pointer-events-none"
          style={pos ? { position: 'absolute', top: pos.top, left: pos.left } : { visibility: 'hidden', position: 'fixed', top: 0, left: 0 }}
        >
          {content}
        </div>
      )}
    </>
  )
}
