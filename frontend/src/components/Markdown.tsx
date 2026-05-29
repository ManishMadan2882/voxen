import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

type Props = { children: string }

const components: Components = {
    p: ({ children }) => <p className="mb-2 last:mb-0 whitespace-pre-wrap">{children}</p>,
    a: ({ children, href }) => (
        <a href={href} target="_blank" rel="noreferrer" className="text-purple-300 underline underline-offset-2 hover:text-purple-200">
            {children}
        </a>
    ),
    ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
    li: ({ children }) => <li className="leading-relaxed">{children}</li>,
    h1: ({ children }) => <h1 className="text-base font-semibold mt-2 mb-1.5">{children}</h1>,
    h2: ({ children }) => <h2 className="text-sm font-semibold mt-2 mb-1.5">{children}</h2>,
    h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
    blockquote: ({ children }) => (
        <blockquote className="border-l-2 border-purple-500/40 pl-3 my-2 text-white/70 italic">{children}</blockquote>
    ),
    hr: () => <hr className="my-3 border-white/10" />,
    table: ({ children }) => (
        <div className="overflow-x-auto my-2">
            <table className="text-xs border-collapse">{children}</table>
        </div>
    ),
    th: ({ children }) => <th className="border border-white/15 px-2 py-1 text-left font-medium">{children}</th>,
    td: ({ children }) => <td className="border border-white/10 px-2 py-1 align-top">{children}</td>,
    code: ({ className, children, ...props }) => {
        const isBlock = /language-/.test(className ?? '')
        if (isBlock) {
            return (
                <code className={`${className ?? ''} block`} {...props}>
                    {children}
                </code>
            )
        }
        return (
            <code className="px-1 py-0.5 rounded bg-white/10 text-purple-200 text-[0.85em]" {...props}>
                {children}
            </code>
        )
    },
    pre: ({ children }) => (
        <pre className="my-2 p-3 rounded-lg bg-black/40 border border-white/10 overflow-x-auto text-xs leading-relaxed">
            {children}
        </pre>
    ),
    strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
}

export const Markdown = ({ children }: Props) => (
    <div className="markdown text-sm leading-relaxed wrap-break-word">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
            {children}
        </ReactMarkdown>
    </div>
)
