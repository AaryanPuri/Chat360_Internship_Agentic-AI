import './App.css'
import Home from './pages/Home'
import Chat from './pages/Chat'
import Integrations from './pages/Integrations'
import Login from './pages/Login'
import Register from './pages/Register'
import Profile from './pages/Profile'
import MessageTypes from './pages/MessageTypes'
import Prompts from './pages/Prompts'
import Functions from './pages/Functions'
import Analytics from './pages/Analytics'
import BotFlowBuilder from './pages/BotFlowBuilder'
import AIAssistant from './pages/AIAssistant'
import SavedBots from './pages/SavedBots'
import KnowledgeBases from "./pages/KnowledgeBases"
import KnowledgeBaseDetail from "./pages/KnowledgeBaseDetail"

import { BrowserRouter as Router, Route, Routes } from 'react-router-dom'


function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/message-types" element={<MessageTypes />} />
        <Route path="/prompts" element={<Prompts />} />
        <Route path="/functions" element={<Functions />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/bot-flow-builder" element={<BotFlowBuilder />} />
        <Route path="/ai-assistant" element={<SavedBots />} />
        <Route path="/ai-assistant/config" element={<AIAssistant />} />
        <Route path="/knowledge-bases" element={<KnowledgeBases />} />
        <Route path="/knowledge-bases/:id" element={<KnowledgeBaseDetail />} />
      </Routes>
    </Router>
  )
}

export default App
