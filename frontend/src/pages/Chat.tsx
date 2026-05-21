import { useState, useRef, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { Markdown } from "../components/Markdown"

type Mode = 'voice' | 'chat'
type Status = 'idle' | 'listening' | 'processing' | 'speaking'
type Source = { source: string; page: number; score: number | null }
type Message = { role: 'user' | 'assistant'; content: string; sources?: Source[] }
type NavItem = 'demo' | 'rag' | 'prompts' | 'agents'
type KbMode = 'file' | 'text' | 'url'

const SUPPORTED_EXTS = ['.pdf', '.docx', '.xlsx', '.xls', '.csv', '.md', '.markdown', '.txt']
type UploadState = 'idle' | 'uploading' | 'done' | 'error'
type Doc = { id: string; file: string; chunks: number }
type CustomPrompt = { id: string; name: string; content: string; created_at: string }
type Agent = { id: string; name: string; prompt_id: string; knowledge_base_id: string; created_at: string }
type ApiKey = {
    id: string
    agent_id: string
    name: string
    key_prefix: string
    is_active: boolean
    created_at: string
    last_used_at: string | null
}

const MODELS = ['llama3.2', 'gemma3']

const NAV: { id: NavItem; label: string; icon: string }[] = [
    { id: 'demo',    label: 'Demo',    icon: '◎' },
    { id: 'rag',     label: 'RAG',     icon: '⬡' },
    { id: 'prompts', label: 'Prompts', icon: '✎' },
    { id: 'agents',  label: 'Agents',  icon: '☄' },
]

export const Chat = () => {
    const [nav, setNav] = useState<NavItem>('demo')

    // ── demo state ───────────────────────────────────────────────
    const [mode, setMode] = useState<Mode>('voice')
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [status, setStatus] = useState<Status>('idle')
    const [liveTranscript, setLiveTranscript] = useState('')
    const [model, setModel] = useState('llama3.2')
    const [selectedSources, setSelectedSources] = useState<string[]>([])
    console.log("sda")
    // ── rag state ────────────────────────────────────────────────
    const [docs, setDocs] = useState<Doc[]>([])
    const [uploadState, setUploadState] = useState<UploadState>('idle')
    const [uploadMsg, setUploadMsg] = useState('')
    const fileInputRef = useRef<HTMLInputElement>(null)
    const [kbMode, setKbMode] = useState<KbMode>('file')
    const [kbInput, setKbInput] = useState('')
    const [kbSource, setKbSource] = useState('')
    const [kbState, setKbState] = useState<UploadState>('idle')
    const [kbMsg, setKbMsg] = useState('')
    const [kbUrl, setKbUrl] = useState('')
    const [urlState, setUrlState] = useState<UploadState>('idle')
    const [urlMsg, setUrlMsg] = useState('')

    // ── prompts state ────────────────────────────────────────────
    const [prompts, setPrompts] = useState<CustomPrompt[]>([])
    const [selectedPromptId, setSelectedPromptId] = useState<string>('')
    const [promptName, setPromptName] = useState('')
    const [promptContent, setPromptContent] = useState('')
    const [promptState, setPromptState] = useState<UploadState>('idle')
    const [promptMsg, setPromptMsg] = useState('')

    // ── agents state ─────────────────────────────────────────────
    const [agents, setAgents] = useState<Agent[]>([])
    const [agentName, setAgentName] = useState('')
    const [agentPromptId, setAgentPromptId] = useState('')
    const [agentKbId, setAgentKbId] = useState('')
    const [agentState, setAgentState] = useState<UploadState>('idle')
    const [agentMsg, setAgentMsg] = useState('')

    // ── publish/api-keys state ───────────────────────────────────
    const [publishAgent, setPublishAgent] = useState<Agent | null>(null)
    const [keys, setKeys] = useState<ApiKey[]>([])
    const [keysLoading, setKeysLoading] = useState(false)
    const [keyName, setKeyName] = useState('')
    const [keyCreating, setKeyCreating] = useState(false)
    const [keyError, setKeyError] = useState('')
    const [newKey, setNewKey] = useState<string>('')
    const [copied, setCopied] = useState(false)
    const [embedCopied, setEmbedCopied] = useState(false)

    const navigate = useNavigate()

    const messagesRef = useRef<Message[]>([])
    const finalTranscriptRef = useRef('')
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => { messagesRef.current = messages }, [messages])
    useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, liveTranscript])

    const fetchDocs = useCallback(async () => {
        try {
            const res = await fetch('http://localhost:8000/rag/documents')
            setDocs(await res.json())
        } catch { /* backend may not be ready yet */ }
    }, [])

    useEffect(() => { fetchDocs() }, [fetchDocs])

    const fetchPrompts = useCallback(async () => {
        try {
            const res = await fetch('http://localhost:8000/prompts')
            const data: CustomPrompt[] = await res.json()
            setPrompts(data)
            setSelectedPromptId(prev => (prev && data.some(p => p.id === prev) ? prev : ''))
        } catch { /* backend may not be ready yet */ }
    }, [])

    useEffect(() => { fetchPrompts() }, [fetchPrompts])

    const handleCreatePrompt = async () => {
        const name = promptName.trim()
        const content = promptContent.trim()
        if (!name || !content) return
        setPromptState('uploading')
        setPromptMsg('Saving…')
        try {
            const res = await fetch('http://localhost:8000/prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, content }),
            })
            if (!res.ok) { const e = await res.json(); throw new Error(e.detail ?? 'Failed') }
            setPromptName('')
            setPromptContent('')
            setPromptState('done')
            setPromptMsg('Saved')
            fetchPrompts()
        } catch (e: any) {
            setPromptState('error')
            setPromptMsg(e.message ?? 'Failed')
        }
    }

    const handleDeletePrompt = async (id: string) => {
        try {
            const res = await fetch(`http://localhost:8000/prompts/${id}`, { method: 'DELETE' })
            if (!res.ok) return
            if (selectedPromptId === id) setSelectedPromptId('')
            fetchPrompts()
        } catch { /* noop */ }
    }

    const fetchAgents = useCallback(async () => {
        try {
            const res = await fetch('http://localhost:8000/agents')
            setAgents(await res.json())
        } catch { /* backend may not be ready yet */ }
    }, [])

    useEffect(() => { fetchAgents() }, [fetchAgents])

    const handleCreateAgent = async () => {
        const name = agentName.trim()
        if (!name || !agentPromptId || !agentKbId) {
            setAgentState('error')
            setAgentMsg('Name, prompt and knowledge base are required.')
            return
        }
        setAgentState('uploading')
        setAgentMsg('Saving…')
        try {
            const res = await fetch('http://localhost:8000/agents', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, prompt_id: agentPromptId, knowledge_base_id: agentKbId }),
            })
            if (!res.ok) { const e = await res.json(); throw new Error(e.detail ?? 'Failed') }
            setAgentName('')
            setAgentPromptId('')
            setAgentKbId('')
            setAgentState('done')
            setAgentMsg('Saved')
            fetchAgents()
        } catch (e: any) {
            setAgentState('error')
            setAgentMsg(e.message ?? 'Failed')
        }
    }

    const handleDeleteAgent = async (id: string) => {
        try {
            const res = await fetch(`http://localhost:8000/agents/${id}`, { method: 'DELETE' })
            if (!res.ok) return
            fetchAgents()
        } catch { /* noop */ }
    }

    const fetchKeys = useCallback(async (agentId: string) => {
        setKeysLoading(true)
        try {
            const res = await fetch(`http://localhost:8000/agents/${agentId}/keys`)
            if (!res.ok) throw new Error('Failed to load keys')
            setKeys(await res.json())
        } catch (e: any) {
            setKeyError(e.message ?? 'Failed to load keys')
        } finally {
            setKeysLoading(false)
        }
    }, [])

    const openPublish = (agent: Agent) => {
        setPublishAgent(agent)
        setKeys([])
        setNewKey('')
        setKeyName('')
        setKeyError('')
        setCopied(false)
        fetchKeys(agent.id)
    }

    const closePublish = () => {
        setPublishAgent(null)
        setKeys([])
        setNewKey('')
        setKeyName('')
        setKeyError('')
        setCopied(false)
    }

    const handleCreateKey = async () => {
        if (!publishAgent) return
        const name = keyName.trim()
        if (!name) { setKeyError('Name is required.'); return }
        setKeyCreating(true)
        setKeyError('')
        try {
            const res = await fetch(`http://localhost:8000/agents/${publishAgent.id}/keys`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name }),
            })
            if (!res.ok) { const e = await res.json(); throw new Error(e.detail ?? 'Failed') }
            const data = await res.json()
            setNewKey(data.key)
            setKeyName('')
            setCopied(false)
            fetchKeys(publishAgent.id)
        } catch (e: any) {
            setKeyError(e.message ?? 'Failed to create key')
        } finally {
            setKeyCreating(false)
        }
    }

    const handleRevokeKey = async (keyId: string) => {
        if (!publishAgent) return
        try {
            const res = await fetch(`http://localhost:8000/agents/${publishAgent.id}/keys/${keyId}`, { method: 'DELETE' })
            if (!res.ok) return
            fetchKeys(publishAgent.id)
        } catch { /* noop */ }
    }

    const copyNewKey = async () => {
        if (!newKey) return
        try {
            await navigator.clipboard.writeText(newKey)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        } catch { /* noop */ }
    }

    const embedSnippet = (key: string, title: string) =>
        `<script src="http://localhost:8000/widget/embed.js" data-key="${key}" data-title="${title.replace(/"/g, '&quot;')}" async></` + `script>`

    const copyEmbed = async () => {
        if (!newKey || !publishAgent) return
        try {
            await navigator.clipboard.writeText(embedSnippet(newKey, publishAgent.name))
            setEmbedCopied(true)
            setTimeout(() => setEmbedCopied(false), 1500)
        } catch { /* noop */ }
    }

    const handleUpload = async (file: File) => {
        const lower = file.name.toLowerCase()
        if (!SUPPORTED_EXTS.some(ext => lower.endsWith(ext))) {
            setUploadMsg(`Unsupported file type. Allowed: ${SUPPORTED_EXTS.join(', ')}`)
            setUploadState('error')
            return
        }
        setUploadState('uploading')
        setUploadMsg(`Uploading ${file.name}…`)
        const form = new FormData()
        form.append('file', file)
        try {
            const res = await fetch('http://localhost:8000/rag/upload', { method: 'POST', body: form })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail ?? 'Upload failed')
            }
            const { chunks } = await res.json()
            setUploadMsg(`${file.name} — ${chunks} chunks indexed`)
            setUploadState('done')
            fetchDocs()
        } catch (e: any) {
            setUploadMsg(e.message ?? 'Upload failed')
            setUploadState('error')
        }
    }

    const handleAddText = async () => {
        if (!kbInput.trim()) return
        setKbState('uploading')
        setKbMsg('Embedding…')
        try {
            const res = await fetch('http://localhost:8000/rag/add-text', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: kbInput.trim(), source: kbSource.trim() || 'manual entry' }),
            })
            if (!res.ok) { const e = await res.json(); throw new Error(e.detail ?? 'Failed') }
            const { chunks } = await res.json()
            setKbMsg(`Indexed ${chunks} chunk${chunks !== 1 ? 's' : ''}`)
            setKbState('done')
            setKbInput('')
            setKbSource('')
            fetchDocs()
        } catch (e: any) {
            setKbMsg(e.message ?? 'Failed')
            setKbState('error')
        }
    }

    const handleAddUrl = async () => {
        const url = kbUrl.trim()
        if (!url) return
        setUrlState('uploading')
        setUrlMsg(`Scraping ${url}…`)
        try {
            const res = await fetch('http://localhost:8000/rag/add-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url }),
            })
            if (!res.ok) { const e = await res.json(); throw new Error(e.detail ?? 'Failed') }
            const { chunks, title } = await res.json()
            setUrlMsg(`${title ?? url} — ${chunks} chunk${chunks !== 1 ? 's' : ''} indexed`)
            setUrlState('done')
            setKbUrl('')
            fetchDocs()
        } catch (e: any) {
            setUrlMsg(e.message ?? 'Failed')
            setUrlState('error')
        }
    }

    // ── shared LLM call ──────────────────────────────────────────
    const send = async (text: string) => {
        if (!text.trim() || status !== 'idle') return
        setStatus('processing')
        setLiveTranscript('')

        const history: Message[] = [...messagesRef.current, { role: 'user', content: text }]
        setMessages([...history, { role: 'assistant', content: '' }])

        try {
            const res = await fetch('http://localhost:8000/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: history,
                    model,
                    ids: selectedSources.length > 0 ? selectedSources : undefined,
                    prompt_id: selectedPromptId || undefined,
                }),
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

    // ── TTS ──────────────────────────────────────────────────────
    const speak = (text: string): Promise<void> =>
        new Promise(resolve => {
            window.speechSynthesis.cancel()
            const utterance = new SpeechSynthesisUtterance(text)
            utterance.onend = () => resolve()
            utterance.onerror = () => resolve()
            window.speechSynthesis.speak(utterance)
        })

    // ── voice input ──────────────────────────────────────────────
    const handleMic = () => {
        if (status === 'speaking') {
            window.speechSynthesis.cancel()
            setStatus('idle')
            return
        }
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

    const toggleSource = (id: string) =>
        setSelectedSources(prev =>
            prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
        )

    return (
        <div className="flex h-screen bg-gray-950 text-white">

            {/* ── Left sidebar ── */}
            <aside className="w-52 shrink-0 border-r border-white/8 flex flex-col">
                {/* Logo */}
                <div className="px-5 py-5 border-b border-white/8">
                    <span className="text-base font-semibold bg-linear-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                        Voxen
                    </span>
                </div>

                {/* Nav items */}
                <nav className="px-2 py-3 space-y-0.5">
                    {NAV.map(item => (
                        <button
                            key={item.id}
                            onClick={() => setNav(item.id)}
                            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-150 ${
                                nav === item.id
                                    ? 'bg-linear-to-r from-purple-600/30 to-blue-600/20 text-white border border-purple-500/20'
                                    : 'text-white/40 hover:text-white/70 hover:bg-white/5'
                            }`}
                        >
                            <span className="text-base leading-none">{item.icon}</span>
                            {item.label}
                        </button>
                    ))}
                </nav>

                {/* KB selector — hidden in agents view (agent metadata takes priority) */}
                {nav !== 'agents' && docs.length > 0 && (
                    <div className="flex-1 overflow-y-auto px-4 py-3 border-t border-white/8">
                        <p className="text-white/30 text-xs mb-2 uppercase tracking-wide">Knowledge Base</p>
                        <div className="space-y-1.5">
                            {docs.map(doc => {
                                const checked = selectedSources.includes(doc.id)
                                return (
                                    <label key={doc.id} className="flex items-start gap-2 cursor-pointer group">
                                        <input
                                            type="checkbox"
                                            checked={checked}
                                            onChange={() => toggleSource(doc.id)}
                                            className="mt-0.5 accent-purple-500 w-3.5 h-3.5 shrink-0 cursor-pointer"
                                        />
                                        <span className={`text-xs leading-snug truncate transition-colors ${checked ? 'text-purple-300' : 'text-white/40 group-hover:text-white/60'}`}>
                                            {doc.file}
                                        </span>
                                    </label>
                                )
                            })}
                        </div>
                        <p className="text-white/20 text-xs mt-2.5">
                            {selectedSources.length === 0
                                ? 'All sources active'
                                : `${selectedSources.length} selected`}
                        </p>
                    </div>
                )}

                {/* Prompt selector — hidden in agents view (agent metadata takes priority) */}
                {nav !== 'agents' && (
                    <div className="px-4 py-4 border-t border-white/8 shrink-0">
                        <p className="text-white/30 text-xs mb-1.5">Prompt</p>
                        <select
                            className="w-full bg-white/5 border border-white/10 text-white/70 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none cursor-pointer"
                            value={selectedPromptId}
                            onChange={e => setSelectedPromptId(e.target.value)}
                            disabled={status !== 'idle'}
                        >
                            <option value="" className="bg-gray-900">Default</option>
                            {prompts.map(p => (
                                <option key={p.id} value={p.id} className="bg-gray-900">{p.name}</option>
                            ))}
                        </select>
                    </div>
                )}

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

                {/* Panel header */}
                <div className="px-6 py-4 border-b border-white/8 shrink-0">
                    <h2 className="text-sm font-medium text-white/60">
                        {nav === 'demo' ? 'Demo'
                            : nav === 'rag' ? 'RAG — Knowledge Base'
                            : nav === 'prompts' ? 'Prompts'
                            : 'Agents'}
                    </h2>
                </div>

                {/* ── Demo panel ── */}
                {nav === 'demo' && (
                    <>
                        {/* Messages */}
                        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3">
                            {messages.length === 0 && !liveTranscript && (
                                <div className="flex items-center justify-center h-full">
                                    <p className="text-white/20 text-sm">
                                        {mode === 'voice' ? 'Tap the mic and start talking' : 'Type a message to start'}
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

                        {/* Input */}
                        <div className="shrink-0 px-6 pb-6 pt-3">
                            {/* Mode toggle */}
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

                            {/* Voice */}
                            {mode === 'voice' && (
                                <div className="flex flex-col items-center gap-2">
                                    <button
                                        onClick={handleMic}
                                        className={`relative w-14 h-14 rounded-full flex items-center justify-center transition-all duration-200 ${
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

                            {/* Chat */}
                            {mode === 'chat' && (
                                <div className="flex gap-2 items-center p-2 rounded-2xl bg-white/5 border border-white/10 focus-within:border-purple-500/50 transition-colors">
                                    <input
                                        className="flex-1 bg-transparent text-white placeholder-white/30 text-sm px-2 py-1.5 focus:outline-none"
                                        type="text"
                                        value={input}
                                        onChange={e => setInput(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleChatSend()}
                                        placeholder="Type a message..."
                                        disabled={status !== 'idle'}
                                        autoFocus
                                    />
                                    <button
                                        className="bg-linear-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-sm font-medium rounded-xl px-4 py-1.5 disabled:opacity-40 transition-all"
                                        onClick={handleChatSend}
                                        disabled={status !== 'idle' || !input.trim()}
                                    >Send</button>
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* ── RAG panel ── */}
                {nav === 'rag' && (
                    <div className="flex-1 flex flex-col min-h-0">

                        {/* Source list */}
                        <div className="flex-1 overflow-y-auto px-6 py-6 max-w-2xl w-full mx-auto">
                            {docs.length > 0 ? (
                                <div>
                                    <p className="text-white/30 text-xs mb-3 uppercase tracking-wide">Indexed documents</p>
                                    <div className="space-y-2">
                                        {docs.map(doc => (
                                            <div
                                                key={doc.file}
                                                className="flex items-center justify-between px-4 py-3 rounded-xl bg-white/5 border border-white/8"
                                            >
                                                <div className="flex items-center gap-3 min-w-0">
                                                    <span className="text-purple-400 text-sm shrink-0">⬡</span>
                                                    <span className="text-white/70 text-sm truncate">{doc.file}</span>
                                                </div>
                                                <span className="text-white/25 text-xs shrink-0 ml-3">{doc.chunks} chunks</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <div className="flex items-center justify-center h-full">
                                    <p className="text-white/20 text-sm">No documents indexed yet — add one below</p>
                                </div>
                            )}
                        </div>

                        {/* Add document — File / Text / URL toggle */}
                        <div className="shrink-0 border-t border-white/8 px-6 py-4 max-w-2xl w-full mx-auto space-y-3">
                            <div className="flex justify-center">
                                <div className="flex gap-1 bg-white/5 p-1 rounded-xl border border-white/10">
                                    {(['file', 'text', 'url'] as KbMode[]).map(m => (
                                        <button key={m} onClick={() => { setKbMode(m); setUploadMsg(''); setKbMsg(''); setUrlMsg('') }}
                                            className={`px-5 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 uppercase tracking-wide ${kbMode === m ? 'bg-linear-to-r from-purple-600 to-blue-600 text-white shadow-md' : 'text-white/40 hover:text-white/70'}`}
                                        >{m}</button>
                                    ))}
                                </div>
                            </div>

                            {kbMode === 'file' && (
                                <div>
                                    <div
                                        className="border border-dashed border-white/15 rounded-2xl px-6 py-7 flex flex-col items-center gap-2 cursor-pointer hover:border-purple-500/40 hover:bg-purple-500/5 transition-all"
                                        onClick={() => { setUploadState('idle'); setUploadMsg(''); fileInputRef.current?.click() }}
                                        onDragOver={e => e.preventDefault()}
                                        onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleUpload(f) }}
                                    >
                                        <span className="text-xl text-white/30">⬡</span>
                                        <p className="text-white/50 text-sm">Drop a file or <span className="text-purple-400">browse</span></p>
                                        <p className="text-white/30 text-xs">PDF, DOCX, XLSX, CSV, MD, TXT</p>
                                        <input ref={fileInputRef} type="file" accept={SUPPORTED_EXTS.join(',')} className="hidden"
                                            onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = '' }} />
                                    </div>
                                    {uploadMsg && (
                                        <p className={`mt-2 text-xs ${uploadState === 'error' ? 'text-red-400' : uploadState === 'done' ? 'text-green-400' : 'text-white/40'}`}>
                                            {uploadState === 'uploading' && <span className="mr-1 animate-spin inline-block">⟳</span>}
                                            {uploadMsg}
                                        </p>
                                    )}
                                </div>
                            )}

                            {kbMode === 'url' && (
                                <div className="space-y-2">
                                    <div className="flex gap-2 items-center p-2 rounded-2xl bg-white/5 border border-white/10 focus-within:border-purple-500/40 transition-colors">
                                        <input
                                            className="flex-1 bg-transparent text-white/80 placeholder-white/25 text-sm px-2 py-1 focus:outline-none"
                                            type="url"
                                            placeholder="https://example.com/article"
                                            value={kbUrl}
                                            onChange={e => setKbUrl(e.target.value)}
                                            onKeyDown={e => { if (e.key === 'Enter') handleAddUrl() }}
                                        />
                                        <button
                                            className="bg-linear-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-xs font-medium rounded-xl px-3 py-1.5 disabled:opacity-40 transition-all shrink-0"
                                            onClick={handleAddUrl}
                                            disabled={!kbUrl.trim() || urlState === 'uploading'}
                                        >{urlState === 'uploading' ? '⟳' : 'Scrape'}</button>
                                    </div>
                                    {urlMsg && (
                                        <p className={`text-xs ${urlState === 'error' ? 'text-red-400' : urlState === 'done' ? 'text-green-400' : 'text-white/40'}`}>
                                            {urlState === 'uploading' && <span className="mr-1 animate-spin inline-block">⟳</span>}
                                            {urlMsg}
                                        </p>
                                    )}
                                </div>
                            )}

                            {kbMode === 'text' && (
                                <div className="space-y-2">
                                    <input
                                        className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white/60 placeholder-white/20 focus:outline-none focus:border-purple-500/40"
                                        placeholder="Source label (e.g. returns-policy)"
                                        value={kbSource}
                                        onChange={e => setKbSource(e.target.value)}
                                    />
                                    <div className="flex gap-2 items-end p-2 rounded-2xl bg-white/5 border border-white/10 focus-within:border-purple-500/40 transition-colors">
                                        <textarea
                                            className="flex-1 bg-transparent text-white/80 placeholder-white/25 text-sm px-2 py-1 focus:outline-none resize-none leading-relaxed"
                                            rows={3}
                                            placeholder="Paste FAQs, policies, product info…"
                                            value={kbInput}
                                            onChange={e => setKbInput(e.target.value)}
                                            onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAddText() }}
                                        />
                                        <button
                                            className="bg-linear-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-xs font-medium rounded-xl px-3 py-1.5 self-end disabled:opacity-40 transition-all shrink-0"
                                            onClick={handleAddText}
                                            disabled={!kbInput.trim() || kbState === 'uploading'}
                                        >{kbState === 'uploading' ? '⟳' : 'Index'}</button>
                                    </div>
                                    {kbMsg && <p className={`text-xs ${kbState === 'error' ? 'text-red-400' : 'text-green-400'}`}>{kbMsg}</p>}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* ── Prompts panel ── */}
                {nav === 'prompts' && (
                    <div className="flex-1 flex flex-col min-h-0">

                        {/* Saved prompts */}
                        <div className="flex-1 overflow-y-auto px-6 py-6 max-w-2xl w-full mx-auto">
                            {prompts.length > 0 ? (
                                <div>
                                    <p className="text-white/30 text-xs mb-3 uppercase tracking-wide">Saved prompts</p>
                                    <div className="space-y-2">
                                        {prompts.map(p => {
                                            const active = selectedPromptId === p.id
                                            return (
                                                <div
                                                    key={p.id}
                                                    className={`px-4 py-3 rounded-xl border ${active ? 'bg-purple-500/10 border-purple-500/30' : 'bg-white/5 border-white/8'}`}
                                                >
                                                    <div className="flex items-center justify-between gap-3">
                                                        <div className="flex items-center gap-3 min-w-0">
                                                            <span className="text-purple-400 text-sm shrink-0">✎</span>
                                                            <span className="text-white/80 text-sm truncate">{p.name}</span>
                                                        </div>
                                                        <div className="flex items-center gap-2 shrink-0">
                                                            <button
                                                                onClick={() => setSelectedPromptId(active ? '' : p.id)}
                                                                className={`text-xs px-2.5 py-1 rounded-md border transition-colors ${active ? 'border-purple-500/40 text-purple-300' : 'border-white/10 text-white/50 hover:text-white/80'}`}
                                                            >{active ? 'Selected' : 'Select'}</button>
                                                            <button
                                                                onClick={() => handleDeletePrompt(p.id)}
                                                                className="text-xs px-2.5 py-1 rounded-md border border-white/10 text-white/40 hover:text-red-400 hover:border-red-400/30 transition-colors"
                                                            >Delete</button>
                                                        </div>
                                                    </div>
                                                    <p className="text-white/40 text-xs mt-2 line-clamp-3 whitespace-pre-wrap">{p.content}</p>
                                                </div>
                                            )
                                        })}
                                    </div>
                                    <p className="text-white/20 text-xs mt-3">
                                        {selectedPromptId ? 'Custom prompt active' : 'Default prompt active'}
                                    </p>
                                </div>
                            ) : (
                                <div className="flex items-center justify-center h-full">
                                    <p className="text-white/20 text-sm">No custom prompts yet — add one below</p>
                                </div>
                            )}
                        </div>

                        {/* New prompt form */}
                        <div className="shrink-0 border-t border-white/8 px-6 py-4 max-w-2xl w-full mx-auto space-y-2">
                            <input
                                className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white/60 placeholder-white/20 focus:outline-none focus:border-purple-500/40"
                                placeholder="Prompt name (e.g. concise-support)"
                                value={promptName}
                                onChange={e => setPromptName(e.target.value)}
                            />
                            <div className="flex gap-2 items-end p-2 rounded-2xl bg-white/5 border border-white/10 focus-within:border-purple-500/40 transition-colors">
                                <textarea
                                    className="flex-1 bg-transparent text-white/80 placeholder-white/25 text-sm px-2 py-1 focus:outline-none resize-none leading-relaxed"
                                    rows={3}
                                    placeholder="System instructions for the assistant…"
                                    value={promptContent}
                                    onChange={e => setPromptContent(e.target.value)}
                                    onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleCreatePrompt() }}
                                />
                                <button
                                    className="bg-linear-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-xs font-medium rounded-xl px-3 py-1.5 self-end disabled:opacity-40 transition-all shrink-0"
                                    onClick={handleCreatePrompt}
                                    disabled={!promptName.trim() || !promptContent.trim() || promptState === 'uploading'}
                                >{promptState === 'uploading' ? '⟳' : 'Save'}</button>
                            </div>
                            {promptMsg && <p className={`text-xs ${promptState === 'error' ? 'text-red-400' : 'text-green-400'}`}>{promptMsg}</p>}
                        </div>
                    </div>
                )}

                {/* ── Agents panel ── */}
                {nav === 'agents' && (
                    <div className="flex-1 flex flex-col min-h-0">

                        {/* Saved agents */}
                        <div className="flex-1 overflow-y-auto px-6 py-6 max-w-2xl w-full mx-auto">
                            {agents.length > 0 ? (
                                <div>
                                    <p className="text-white/30 text-xs mb-3 uppercase tracking-wide">Agents</p>
                                    <div className="space-y-2">
                                        {agents.map(a => {
                                            const promptLabel = prompts.find(p => p.id === a.prompt_id)?.name ?? a.prompt_id
                                            const kbLabel = docs.find(d => d.id === a.knowledge_base_id)?.file ?? a.knowledge_base_id
                                            return (
                                                <div
                                                    key={a.id}
                                                    className="px-4 py-3 rounded-xl border bg-white/5 border-white/8"
                                                >
                                                    <div className="flex items-center justify-between gap-3">
                                                        <div className="flex items-center gap-3 min-w-0">
                                                            <span className="text-purple-400 text-sm shrink-0">☄</span>
                                                            <span className="text-white/80 text-sm truncate">{a.name}</span>
                                                        </div>
                                                        <div className="flex items-center gap-2 shrink-0">
                                                            <button
                                                                onClick={() => navigate(`/agents/${a.id}`)}
                                                                className="text-xs px-2.5 py-1 rounded-md border border-purple-500/40 text-purple-300 hover:bg-purple-500/10 transition-colors"
                                                            >Open</button>
                                                            <button
                                                                onClick={() => openPublish(a)}
                                                                className="text-xs px-2.5 py-1 rounded-md bg-linear-to-r from-purple-600 to-blue-600 text-white hover:from-purple-500 hover:to-blue-500 transition-all"
                                                            >Publish</button>
                                                            <button
                                                                onClick={() => handleDeleteAgent(a.id)}
                                                                className="text-xs px-2.5 py-1 rounded-md border border-white/10 text-white/40 hover:text-red-400 hover:border-red-400/30 transition-colors"
                                                            >Delete</button>
                                                        </div>
                                                    </div>
                                                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-white/40">
                                                        <span>Prompt: <span className="text-white/60">{promptLabel}</span></span>
                                                        <span>KB: <span className="text-white/60">{kbLabel}</span></span>
                                                    </div>
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>
                            ) : (
                                <div className="flex items-center justify-center h-full">
                                    <p className="text-white/20 text-sm">No agents yet — create one below</p>
                                </div>
                            )}
                        </div>

                        {/* New agent form */}
                        <div className="shrink-0 border-t border-white/8 px-6 py-4 max-w-2xl w-full mx-auto space-y-2">
                            <input
                                className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white/60 placeholder-white/20 focus:outline-none focus:border-purple-500/40"
                                placeholder="Agent name (e.g. support-bot)"
                                value={agentName}
                                onChange={e => setAgentName(e.target.value)}
                            />
                            <div className="grid grid-cols-2 gap-2">
                                <select
                                    className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white/70 focus:outline-none focus:border-purple-500/40 cursor-pointer"
                                    value={agentPromptId}
                                    onChange={e => setAgentPromptId(e.target.value)}
                                >
                                    <option value="" className="bg-gray-900">Select prompt…</option>
                                    {prompts.map(p => (
                                        <option key={p.id} value={p.id} className="bg-gray-900">{p.name}</option>
                                    ))}
                                </select>
                                <select
                                    className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white/70 focus:outline-none focus:border-purple-500/40 cursor-pointer"
                                    value={agentKbId}
                                    onChange={e => setAgentKbId(e.target.value)}
                                >
                                    <option value="" className="bg-gray-900">Select knowledge base…</option>
                                    {docs.map(d => (
                                        <option key={d.id} value={d.id} className="bg-gray-900">{d.file}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex justify-end">
                                <button
                                    className="bg-linear-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-xs font-medium rounded-xl px-3 py-1.5 disabled:opacity-40 transition-all"
                                    onClick={handleCreateAgent}
                                    disabled={!agentName.trim() || !agentPromptId || !agentKbId || agentState === 'uploading'}
                                >{agentState === 'uploading' ? '⟳' : 'Create agent'}</button>
                            </div>
                            {agentMsg && <p className={`text-xs ${agentState === 'error' ? 'text-red-400' : 'text-green-400'}`}>{agentMsg}</p>}
                            {(prompts.length === 0 || docs.length === 0) && (
                                <p className="text-white/30 text-xs">
                                    {prompts.length === 0 && 'Create a prompt first.'} {docs.length === 0 && 'Add a knowledge base entry first.'}
                                </p>
                            )}
                        </div>
                    </div>
                )}

            </div>

            {publishAgent && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
                    onClick={closePublish}
                >
                    <div
                        className="w-full max-w-2xl max-h-[85vh] flex flex-col bg-gray-900 border border-white/10 rounded-2xl shadow-2xl"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between px-6 py-4 border-b border-white/8 shrink-0">
                            <div className="min-w-0">
                                <p className="text-white/30 text-xs uppercase tracking-wide">Publish agent</p>
                                <p className="text-white text-sm font-medium truncate">{publishAgent.name}</p>
                            </div>
                            <button
                                onClick={closePublish}
                                className="text-white/40 hover:text-white text-lg leading-none px-2"
                            >×</button>
                        </div>

                        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
                            {newKey && (
                                <div className="p-4 rounded-xl border border-purple-500/40 bg-purple-500/10 space-y-2">
                                    <p className="text-purple-200 text-xs uppercase tracking-wide">New API key — copy it now</p>
                                    <p className="text-white/50 text-xs">This key is shown only once. Store it securely; it cannot be retrieved later.</p>
                                    <div className="flex gap-2 items-center p-2 rounded-lg bg-gray-950/60 border border-white/10">
                                        <code className="flex-1 text-purple-200 text-xs break-all font-mono">{newKey}</code>
                                        <button
                                            onClick={copyNewKey}
                                            className="text-xs px-2.5 py-1 rounded-md bg-linear-to-r from-purple-600 to-blue-600 text-white hover:from-purple-500 hover:to-blue-500 transition-all shrink-0"
                                        >{copied ? 'Copied' : 'Copy'}</button>
                                    </div>
                                </div>
                            )}

                            {newKey && publishAgent && (
                                <div className="p-4 rounded-xl border border-white/10 bg-white/5 space-y-2">
                                    <p className="text-white/60 text-xs uppercase tracking-wide">Embed snippet</p>
                                    <p className="text-white/40 text-xs">Paste this on your site to render the chat widget. Visitors will see a chat bubble that opens the agent — nothing about prompts, knowledge bases, or the agent owner is exposed.</p>
                                    <div className="flex gap-2 items-start p-2 rounded-lg bg-gray-950/60 border border-white/10">
                                        <code className="flex-1 text-white/80 text-xs break-all font-mono whitespace-pre-wrap">{embedSnippet(newKey, publishAgent.name)}</code>
                                        <button
                                            onClick={copyEmbed}
                                            className="text-xs px-2.5 py-1 rounded-md border border-white/10 text-white/70 hover:text-white hover:border-white/30 transition-colors shrink-0"
                                        >{embedCopied ? 'Copied' : 'Copy'}</button>
                                    </div>
                                </div>
                            )}

                            <div className="space-y-2">
                                <p className="text-white/30 text-xs uppercase tracking-wide">Create new key</p>
                                <div className="flex gap-2 items-center p-2 rounded-2xl bg-white/5 border border-white/10 focus-within:border-purple-500/40 transition-colors">
                                    <input
                                        className="flex-1 bg-transparent text-white/80 placeholder-white/25 text-sm px-2 py-1 focus:outline-none"
                                        type="text"
                                        placeholder="Key name (e.g. production)"
                                        value={keyName}
                                        onChange={e => setKeyName(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter') handleCreateKey() }}
                                    />
                                    <button
                                        onClick={handleCreateKey}
                                        disabled={!keyName.trim() || keyCreating}
                                        className="bg-linear-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-xs font-medium rounded-xl px-3 py-1.5 disabled:opacity-40 transition-all shrink-0"
                                    >{keyCreating ? '⟳' : 'Create key'}</button>
                                </div>
                                {keyError && <p className="text-xs text-red-400">{keyError}</p>}
                            </div>

                            <div className="space-y-2">
                                <p className="text-white/30 text-xs uppercase tracking-wide">Existing keys</p>
                                {keysLoading ? (
                                    <p className="text-white/30 text-xs">Loading…</p>
                                ) : keys.length === 0 ? (
                                    <p className="text-white/30 text-xs">No keys yet.</p>
                                ) : (
                                    <div className="overflow-x-auto rounded-xl border border-white/8">
                                        <table className="w-full text-xs">
                                            <thead className="bg-white/5 text-white/40 uppercase tracking-wide">
                                                <tr>
                                                    <th className="text-left font-normal px-3 py-2">Name</th>
                                                    <th className="text-left font-normal px-3 py-2">Prefix</th>
                                                    <th className="text-left font-normal px-3 py-2">Created</th>
                                                    <th className="text-left font-normal px-3 py-2">Last used</th>
                                                    <th className="px-3 py-2"></th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-white/8">
                                                {keys.map(k => (
                                                    <tr key={k.id} className="text-white/70">
                                                        <td className="px-3 py-2 truncate max-w-40">{k.name}</td>
                                                        <td className="px-3 py-2 font-mono text-purple-300">{k.key_prefix}…</td>
                                                        <td className="px-3 py-2 text-white/50">{new Date(k.created_at).toLocaleDateString()}</td>
                                                        <td className="px-3 py-2 text-white/50">{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : '—'}</td>
                                                        <td className="px-3 py-2 text-right">
                                                            <button
                                                                onClick={() => handleRevokeKey(k.id)}
                                                                className="text-xs px-2 py-0.5 rounded-md border border-white/10 text-white/40 hover:text-red-400 hover:border-red-400/30 transition-colors"
                                                            >Revoke</button>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
