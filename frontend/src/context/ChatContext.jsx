import React, { createContext, useContext, useState, useEffect } from 'react';
import { askChat } from '../services/api';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem('pilgrim_session_id') || `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  });
  const [isFullChatOpen, setIsFullChatOpen] = useState(false);

  useEffect(() => {
    if (sessionId) {
      localStorage.setItem('pilgrim_session_id', sessionId);
    }
  }, [sessionId]);

  const startNewSession = () => {
    const freshId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    localStorage.setItem('pilgrim_session_id', freshId);
    setSessionId(freshId);
    setMessages([]);
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  };

  const sendMessage = async (questionText) => {
    const q = (questionText || '').trim();
    if (!q || isLoading) return;

    const userMsg = { role: 'user', content: q, timestamp: new Date().toLocaleTimeString() };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await askChat(q, sessionId);
      if (res.session_id) {
        setSessionId(res.session_id);
        localStorage.setItem('pilgrim_session_id', res.session_id);
      }

      const botMsg = {
        role: 'assistant',
        content: res.answer,
        agentName: res.agent_name || 'PilgrimAI Specialist',
        confidence: res.confidence_score ? Math.round(res.confidence_score * 100) : null,
        latencyMs: res.latency_ms,
        sources: res.sources || [],
        chunks: res.retrieved_chunks || [],
        metadata: res.metadata || {},
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      const errMsg = {
        role: 'assistant',
        content: `Error: ${err.message || 'Unable to complete offline chat request. Ensure backend is running.'}`,
        isError: true,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ChatContext.Provider
      value={{
        messages,
        isLoading,
        sessionId,
        isFullChatOpen,
        setIsFullChatOpen,
        startNewSession,
        sendMessage,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
