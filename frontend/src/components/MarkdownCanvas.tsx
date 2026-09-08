import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Check, Copy } from 'lucide-react'
import clsx from 'clsx'

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1 rounded-xs px-2 py-0.5 text-[10px] font-medium text-muted hover:bg-hairline hover:text-ink transition-colors"
    >
      {copied
        ? <><Check className="h-3 w-3 text-deep-green" /> Copied</>
        : <><Copy className="h-3 w-3" /> Copy</>}
    </button>
  )
}

interface Props {
  content: string
  className?: string
}

export function MarkdownCanvas({ content, className }: Props) {
  return (
    <div className={clsx('markdown-canvas text-sm leading-relaxed text-ink', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{

          // ── Headings ──────────────────────────────────────────────────────────
          h1: ({ children }) => (
            <h1 className="mt-6 mb-3 text-xl font-semibold tracking-tight text-ink first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-5 mb-2.5 text-base font-semibold tracking-tight text-ink first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-4 mb-2 text-sm font-semibold text-ink first:mt-0">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="mt-3 mb-1.5 text-sm font-medium text-slate first:mt-0">
              {children}
            </h4>
          ),

          // ── Paragraph ─────────────────────────────────────────────────────────
          p: ({ children }) => (
            <p className="mb-3 last:mb-0 leading-[1.75]">{children}</p>
          ),

          // ── Bold / Italic / Strike ────────────────────────────────────────────
          strong: ({ children }) => (
            <strong className="font-semibold text-ink">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="italic text-body-muted">{children}</em>
          ),
          del: ({ children }) => (
            <del className="text-muted line-through">{children}</del>
          ),

          // ── Lists ─────────────────────────────────────────────────────────────
          ul: ({ children }) => (
            <ul className="mb-3 space-y-1 pl-5 last:mb-0 list-disc marker:text-muted">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3 space-y-1 pl-5 last:mb-0 list-decimal marker:text-muted marker:font-medium">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-[1.7] pl-0.5">{children}</li>
          ),

          // ── Horizontal rule ───────────────────────────────────────────────────
          hr: () => <hr className="my-5 border-hairline" />,

          // ── Blockquote ────────────────────────────────────────────────────────
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-4 border-action-blue/30 pl-4 text-muted italic">
              {children}
            </blockquote>
          ),

          // ── Inline code ───────────────────────────────────────────────────────
          code: ({ children, className: cls }) => {
            const isBlock = cls?.startsWith('language-')
            if (isBlock) return <>{children}</>
            return (
              <code className="rounded-xs bg-stone px-1.5 py-0.5 font-mono text-[12px] text-ink">
                {children}
              </code>
            )
          },

          // ── Fenced code block ─────────────────────────────────────────────────
          pre: ({ children }) => {
            const codeEl = React.Children.toArray(children).find(
              c => React.isValidElement(c) && c.type === 'code',
            ) as React.ReactElement | undefined

            const rawText =
              typeof codeEl?.props?.children === 'string'
                ? codeEl.props.children
                : String(codeEl?.props?.children ?? '')

            return (
              <div className="group relative my-4 overflow-hidden rounded-sm border border-hairline bg-stone">
                <div className="flex items-center justify-between border-b border-hairline px-3 py-1.5">
                  <span className="font-mono text-[10px] text-muted uppercase tracking-wide">
                    {codeEl?.props?.className?.replace('language-', '') || 'code'}
                  </span>
                  <CopyButton text={rawText} />
                </div>
                <pre className="overflow-x-auto px-4 py-3 font-mono text-[12.5px] leading-relaxed text-ink">
                  <code>{codeEl?.props?.children}</code>
                </pre>
              </div>
            )
          },

          // ── Table ─────────────────────────────────────────────────────────────
          table: ({ children }) => (
            <div className="my-4 w-full overflow-x-auto rounded-sm border border-hairline">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-stone border-b border-hairline">{children}</thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-hairline">{children}</tbody>
          ),
          tr: ({ children }) => (
            <tr className="transition-colors hover:bg-stone/50">{children}</tr>
          ),
          th: ({ children }) => (
            <th className="px-4 py-2.5 text-left font-mono text-[10px] font-semibold uppercase tracking-wider text-slate whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-2.5 text-sm text-ink">
              {children}
            </td>
          ),

          // ── Link ──────────────────────────────────────────────────────────────
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-action-blue underline underline-offset-2 hover:text-action-blue/80"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
