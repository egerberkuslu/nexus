import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/utils/cn'

export type MarkdownViewerProps = {
  value: string
  placeholder?: string
  className?: string
  variant?: 'card' | 'plain'
}

export default function MarkdownViewer({ value, placeholder, className, variant = 'card' }: MarkdownViewerProps) {
  const content = String(value || '').trim()
  if (!content) {
    if (variant === 'plain') {
      return (
        <div className={cn('text-sm text-gray-600 dark:text-gray-400', className)}>
          {placeholder || 'Nothing to show yet.'}
        </div>
      )
    }
    return (
      <div
        className={cn(
          'rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900',
          'px-4 py-3 text-sm text-gray-600 dark:text-gray-400',
          className
        )}
      >
        {placeholder || 'Nothing to show yet.'}
      </div>
    )
  }

  return (
    <div
      className={cn(
        variant === 'plain'
          ? ''
          : 'rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-4 py-3',
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mt-2 mb-2" {...props} />,
          h2: (props) => <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-4 mb-2" {...props} />,
          h3: (props) => <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mt-4 mb-2" {...props} />,
          p: (props) => <p className="text-sm leading-6 text-gray-800 dark:text-gray-200 my-2" {...props} />,
          ul: (props) => <ul className="list-disc pl-6 my-2 space-y-1 text-sm text-gray-800 dark:text-gray-200" {...props} />,
          ol: (props) => <ol className="list-decimal pl-6 my-2 space-y-1 text-sm text-gray-800 dark:text-gray-200" {...props} />,
          li: (props) => <li className="leading-6" {...props} />,
          a: (props) => (
            <a
              className="text-blue-600 dark:text-blue-400 font-medium underline underline-offset-2"
              target="_blank"
              rel="noreferrer"
              {...props}
            />
          ),
          hr: (props) => <hr className="my-4 border-gray-200 dark:border-gray-800" {...props} />,
          blockquote: (props) => (
            <blockquote
              className="my-3 border-l-4 border-blue-200 dark:border-blue-800 pl-4 text-sm text-gray-700 dark:text-gray-300"
              {...props}
            />
          ),
          table: (props) => (
            <div className="my-3 overflow-auto">
              <table className="w-full text-sm border-collapse" {...props} />
            </div>
          ),
          thead: (props) => <thead className="text-xs text-gray-600 dark:text-gray-400" {...props} />,
          th: (props) => <th className="text-left py-2 px-2 border-b border-gray-200 dark:border-gray-800" {...props} />,
          td: (props) => <td className="py-2 px-2 border-b border-gray-100 dark:border-gray-800/60 align-top" {...props} />,
          code: ({ className: codeClass, children, ...props }) => {
            const isBlock = typeof codeClass === 'string' && codeClass.includes('language-')
            if (isBlock) {
              return (
                <code
                  className={cn(
                    'block text-xs font-mono text-gray-900 dark:text-gray-100',
                    'bg-gray-50 dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-xl p-3 overflow-auto',
                    codeClass
                  )}
                  {...props}
                >
                  {children}
                </code>
              )
            }
            return (
              <code
                className="text-xs font-mono px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                {...props}
              >
                {children}
              </code>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
