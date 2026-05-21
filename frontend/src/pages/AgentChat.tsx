import { useState, useRef, useEffect, useCallback } from "react"
import { Link, useParams } from "react-router-dom"
import { Markdown } from "../components/Markdown"

type Mode = 'voice' | 'chat'
type Status = 'idle' | 'listening' | 'processing' | 'speaking'
type Source = { source: string; page: number; score: number | null }
type Message = { role: 'user' | 'assistant'; content: string; sources?: Source[] }
type Agent = { id: string; name: string; prompt_id: string; knowledge_base_id: string; created_at: string }
type Doc = { id: string; file: string; chunks: number }
type CustomPrompt = { id: string; name: string; content: string; created_at: string }

const MODELS = ['llama3.2', 'gemma3']

export const AgentChat = () => {
    const { agentId = '' } = useParams<{ agentId: string }>()

    const [agent, setAgent] = useState<Agent | null>(null)
    const [agentError, setAgentError] = useState('')
    const [promptName, setPromptName] = useState('')
    const [kbLabel, setKbLabel] = useState('')

    const [mode, setMode] = useState<Mode>('chat')
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [status, setStatus] = useState<Status>('idle')
    const [liveTranscript, setLiveTranscript] = useState('')
    const [model, setModel] = useState('llama3.2')

    const messagesRef = useRef<Message[]>([])
    const finalTranscriptRef = useRef('')
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => { messagesRef.current = messages }, [messages])
    useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, liveTranscript])

    const loadAgent = useCallback(async () => {
        try {
            const res = await fetch('http://localhost:8000/agents')
            const list: Agent[] = await res.json()
            const found = list.find(a => a.id === agentId) ?? null
            setAgent(found)
            if (!found) { setAgentError('Agent not found.'); return }

            const [pRes, dRes] = await Promise.all([
                fetch('http://localhost:8000/prompts'),
                fetch('http://localhost:8000/rag/documents'),
            ])
            const prompts: CustomPrompt[] = await pRes.json()
            const docs: Doc[] = await dRes.json()
            setPromptName(prompts.find(p => p.id === found.prompt_id)?.name ?? found.prompt_id)
            setKbLabel(docs.find(d => d.id === found.knowledge_base_id)?.file ?? found.knowledge_base_id)
        } catch {
            setAgentError('Failed to load agent.')
        }
    }, [agentId])

    useEffect(() => { loadAgent() }, [loadAgent])

    const send = async (text: string) => {
        if (!text.trim() || status !== 'idle' || !agent) return
        setStatus('processing')
        setLiveTranscript('')

        const history: Message[] = [...messagesRef.current, { role: 'user', content: text }]
        setMessages([...history, { role: 'assistant', content: '' }])

        try {
            const res = await fetch(`http://localhost:8000/agents/${agent.id}/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: history, model }),
            })

            const reader = res.body!.getReader()
            const decoder = new TextDecoder()
            let buffer = ''
            let fullResponse = ''
            let eventType = 'message'

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop()!
                for (const line of lines) {
                    if (line.startsWith('event: ')) { eventType = line.slice(7).trim(); continue }
                    if (!line.startsWith('data: ')) continue
                    const data = line.slice(6)
                    if (eventType === 'sources') {
                        const sources: Source[] = JSON.parse(data)
                        setMessages(prev => {
                            const msgs = [...prev]
                            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], sources }
                            return msgs
                        })
                        eventType = 'message'
                        continue
                    }
                    if (data === '[DONE]') break
                    fullResponse += data
                    setMessages(prev => {
                        const msgs = [...prev]
                        msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content: fullResponse }
                        return msgs
                    })
                }
            }

            if (mode === 'voice') {
                setStatus('speaking')
                await speak(fullResponse)
            }
        } catch {
            setMessages(prev => {
                const msgs = [...prev]
                msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content: 'Error: failed to connect.' }
                return msgs
            })
        } finally {
            setStatus('idle')
        }
    }

    const speak = (text: string): Promise<void> =>
        new Promise(resolve => {
            window.speechSynthesis.cancel()
            const utterance = new SpeechSynthesisUtterance(text)
            utterance.onend = () => resolve()
            utterance.onerror = () => resolve()
            window.speechSynthesis.speak(utterance)
        })

    const handleMic = () => {
        if (status === 'speaking') { window.speechSynthesis.cancel(); setStatus('idle'); return }
        if (status !== 'idle') return
        const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
        if (!SR) { alert('Speech recognition not supported. Use Chrome.'); return }
        finalTranscriptRef.current = ''
        const recognition = new SR()
        recognition.continuous = false
        recognition.interimResults = true
        recognition.lang = 'en-US'
        recognition.onstart = () => setStatus('listening')
        recognition.onresult = (e: any) => {
            let interim = ''
            for (let i = e.resultIndex; i < e.results.length; i++) {
                const t = e.results[i][0].transcript
                if (e.results[i].isFinal) finalTranscriptRef.current += t
                else interim += t
            }
            setLiveTranscript(finalTranscriptRef.current + interim)
        }
        recognition.onend = () => {
            const text = finalTranscriptRef.current.trim()
            if (text) send(text)
            else { setStatus('idle'); setLiveTranscript('') }
        }
        recognition.onerror = () => { setStatus('idle'); setLiveTranscript('') }
        recognition.start()
    }


    const handleChatSend = () => { send(input.trim()); setInput('') }

    const statusLabel: Record<Status, string> = {
        idle: 'Tap to speak',
        listening: 'Listening...',
        processing: 'Thinking...',
        speaking: 'Speaking — tap to stop',
    }

    return (
        <div className="flex h-screen bg-gray-950 text-white">

            {/* ── Left sidebar ── */}
            <aside className="w-60 shrink-0 border-r border-white/8 flex flex-col">
                <div className="px-5 py-5 border-b border-white/8">
                    <Link to="/" className="text-xs text-white/40 hover:text-white/70 transition-colors">← Dashboard</Link>
                </div>

                <div className="px-4 py-4 border-b border-white/8">
                    <p className="text-white/30 text-xs mb-1.5 uppercase tracking-wide">Agent</p>
                    <p className="text-white text-sm font-medium truncate">{agent?.name ?? (agentError || 'Loading…')}</p>
                </div>

                {agent && (
                    <div className="px-4 py-4 border-b border-white/8 space-y-3">
                        <div>
                            <p className="text-white/30 text-xs mb-1 uppercase tracking-wide">Prompt</p>
                            <p className="text-white/70 text-xs truncate">{promptName || '—'}</p>
                        </div>
                        <div>
                            <p className="text-white/30 text-xs mb-1 uppercase tracking-wide">Knowledge Base</p>
                            <p className="text-white/70 text-xs truncate">{kbLabel || '—'}</p>
                        </div>
                    </div>
                )}

                <div className="flex-1" />

                {/* Model selector */}
                <div className="px-4 py-4 border-t border-white/8 shrink-0">
                    <p className="text-white/30 text-xs mb-1.5">Model</p>
                    <select
                        className="w-full bg-white/5 border border-white/10 text-white/70 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none cursor-pointer"
                        value={model}
                        onChange={e => setModel(e.target.value)}
                        disabled={status !== 'idle'}
                    >
                        {MODELS.map(m => <option key={m} value={m} className="bg-gray-900">{m}</option>)}
                    </select>
                </div>
            </aside>

            {/* ── Right panel ── */}
            <div className="flex-1 flex flex-col min-w-0 min-h-0">
                <div className="px-6 py-4 border-b border-white/8 shrink-0">
                    <h2 className="text-sm font-medium text-white/60">{agent ? `Chat — ${agent.name}` : 'Agent'}</h2>
                </div>

                <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3">
                    {messages.length === 0 && !liveTranscript && (
                        <div className="flex items-center justify-center h-full">
                            <p className="text-white/20 text-sm">
                                {agentError || (mode === 'voice' ? 'Tap the mic and start talking' : 'Type a message to start')}
                            </p>
                        </div>
                    )}
                    {messages.map((msg, i) => (
                        <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                            <div className={`rounded-2xl px-4 py-2.5 max-w-[75%] text-sm leading-relaxed ${
                                msg.role === 'user'
                                    ? 'bg-linear-to-br from-purple-600 to-blue-600 text-white shadow-lg shadow-purple-500/20 whitespace-pre-wrap'
                                    : 'bg-white/5 text-white/85 border border-white/10'
                            }`}>
                                {msg.role === 'assistant'
                                    ? (msg.content
                                        ? <Markdown>{msg.content}</Markdown>
                                        : (status === 'processing' && i === messages.length - 1
                                            ? <span className="animate-pulse text-purple-400">▌</span>
                                            : ''))
                                    : msg.content}
                            </div>
                            {msg.sources && msg.sources.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mt-1.5 max-w-[75%]">
                                    {msg.sources.map((s, j) => (
                                        <span key={j} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs">
                                            <span className="opacity-50">⬡</span>
                                            {s.source} p.{s.page}
                                            {s.score != null && <span className="opacity-40 ml-0.5">{s.score}</span>}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                    {liveTranscript && (
                        <div className="flex justify-end">
                            <div className="rounded-2xl px-4 py-2.5 max-w-[75%] text-sm bg-purple-900/30 text-white/40 border border-purple-500/20 italic">
                                {liveTranscript}
                            </div>
                        </div>
                    )}
                    <div ref={bottomRef} />
                </div>

                <div className="shrink-0 px-6 pb-6 pt-3">
                    <div className="flex justify-center mb-4">
                        <div className="flex gap-1 bg-white/5 p-1 rounded-xl border border-white/10">
                            {(['voice', 'chat'] as Mode[]).map(m => (
                                <button
                                    key={m}
                                    onClick={() => setMode(m)}
                                    disabled={status !== 'idle'}
                                    className={`px-5 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 capitalize ${
                                        mode === m
                                            ? 'bg-linear-to-r from-purple-600 to-blue-600 text-white shadow-md'
                                            : 'text-white/40 hover:text-white/70'
                                    }`}
                                >{m}</button>
                            ))}
                        </div>
                    </div>

                    {mode === 'voice' && (
                        <div className="flex flex-col items-center gap-2">
                            <button
                                onClick={handleMic}
                                disabled={!agent}
                                className={`relative w-14 h-14 rounded-full flex items-center justify-center transition-all duration-200 disabled:opacity-40 ${
                                    status === 'listening'
                                        ? 'bg-red-500 shadow-xl shadow-red-500/40 scale-110'
                                        : status === 'speaking'
                                        ? 'bg-linear-to-br from-purple-500 to-blue-500 shadow-xl shadow-purple-500/30 scale-105'
                                        : 'bg-linear-to-br from-purple-600 to-blue-600 shadow-lg shadow-purple-500/20 hover:scale-105 active:scale-95'
                                }`}
                            >
                                {status === 'listening' && (
                                    <span className="absolute inset-0 rounded-full bg-red-400 animate-ping opacity-25" />
                                )}
                                {status === 'processing' ? (
                                    <svg className="w-5 h-5 text-white animate-spin" viewBox="0 0 24 24" fill="none">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                ) : (
                                    <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M12 2a3 3 0 00-3 3v7a3 3 0 006 0V5a3 3 0 00-3-3z" />
                                        <path d="M19 11a1 1 0 10-2 0 5 5 0 01-10 0 1 1 0 10-2 0 7 7 0 0012 0zM11 19.93V22h-2a1 1 0 100 2h6a1 1 0 100-2h-2v-2.07A7.001 7.001 0 0019 13a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7.001 7.001 0 006 6.93z" />
                                    </svg>
                                )}
                            </button>
                            <p className="text-white/30 text-xs">{statusLabel[status]}</p>
                        </div>
                    )}

                    {mode === 'chat' && (
                        <div className="flex gap-2 items-center p-2 rounded-2xl bg-white/5 border border-white/10 focus-within:border-purple-500/50 transition-colors">
                            <input
                                className="flex-1 bg-transparent text-white placeholder-white/30 text-sm px-2 py-1.5 focus:outline-none"
                                type="text"
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && handleChatSend()}
                                placeholder="Type a message..."
                                disabled={status !== 'idle' || !agent}
                                autoFocus
                            />
                            <button
                                className="bg-linear-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-sm font-medium rounded-xl px-4 py-1.5 disabled:opacity-40 transition-all"
                                onClick={handleChatSend}
                                disabled={status !== 'idle' || !input.trim() || !agent}
                            >Send</button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
