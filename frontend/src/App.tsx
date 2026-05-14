import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Chat } from './pages/Chat'
import { AgentChat } from './pages/AgentChat'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/agents/:agentId" element={<AgentChat />} />
        <Route path="*" element={<Chat />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
