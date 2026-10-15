import React, { useState, useRef, useEffect } from 'react';
import { Sparkles, ChevronRight, Send, Loader2, Maximize2, RotateCcw } from 'lucide-react';
import { useChat } from '../context/ChatContext';
import StructuredCards from './StructuredCards';

export default function AskPilgrimAI() {
  const { 
    messages, 
    isLoading, 
    sendMessage, 
    startNewSession, 
    setIsFullChatOpen 
  } = useChat();

  const [inputVal, setInputVal] = useState('');
  const chatScrollRef = useRef(null);

  const sampleChips = [
    'What are the timings of Yadadri temple?',
    'Plan a 2 day trip to Tirupati under ₹5000',
    'Best time to visit Ramappa temple?',
    'Show me temples near Hyderabad',
  ];

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = (text) => {
    const q = (text || inputVal).trim();
    if (!q || isLoading) return;
    setInputVal('');
    sendMessage(q);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleSend();
  };

  return (
    <div className="ask-pilgrim-card">
      <div className="ask-header-row" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles className="ask-sparkle-icon" />
          <h3 className="ask-header-title">Ask PilgrimAI</h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button 
            type="button" 
            className="icon-badge-btn" 
            style={{ width: 28, height: 28 }} 
            onClick={startNewSession}
            title="Start New Conversation"
          >
            <RotateCcw size={13} />
          </button>
          <button 
            type="button" 
            className="icon-badge-btn" 
            style={{ width: 28, height: 28 }} 
            onClick={() => setIsFullChatOpen(true)}
            title="Expand to Full Chat Interface"
          >
            <Maximize2 size={13} />
          </button>
        </div>
      </div>

      <p className="ask-subtitle">
        Get instant answers about temples, travel, timings, accommodation and more.
      </p>

      {/* Suggested Prompt Chips */}
      {messages.length === 0 && (
        <div className="prompt-chips-list">
          {sampleChips.map((chip, idx) => (
            <button
              key={idx}
              className="prompt-chip-btn"
              onClick={() => handleSend(chip)}
              disabled={isLoading}
              type="button"
            >
              <span>{chip}</span>
              <ChevronRight className="prompt-chip-arrow" />
            </button>
          ))}
        </div>
      )}

      {/* Conversation Thread */}
      {messages.length > 0 && (
        <div 
          className="chat-conversation-area" 
          ref={chatScrollRef}
          style={{ minHeight: 140, maxHeight: 260 }}
        >
          {messages.map((msg, i) => (
            <div key={i} className={`chat-bubble ${msg.role}`}>
              {msg.role === 'assistant' && (
                <div className="chat-meta-bar">
                  {msg.agentName && (
                    <span className="agent-badge">{msg.agentName}</span>
                  )}
                  {msg.confidence !== null && (
                    <span className="confidence-badge">{msg.confidence}% match</span>
                  )}
                  {msg.latencyMs && (
                    <span style={{ color: '#888' }}>({msg.latencyMs}ms)</span>
                  )}
                </div>
              )}
              
              <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

              {msg.metadata && <StructuredCards metadata={msg.metadata} />}

              {msg.sources && msg.sources.length > 0 && (
                <details className="sources-accordion">
                  <summary>Verified Sources ({msg.sources.length})</summary>
                  <ul className="sources-list">
                    {msg.sources.map((s, si) => (
                      <li key={si}>{s}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="chat-bubble assistant" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Loader2 size={16} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
              <span>Consulting offline RAG agents...</span>
            </div>
          )}
        </div>
      )}

      {/* Chat Input Bar */}
      <form onSubmit={handleSubmit} className="ask-input-form" style={{ marginTop: 8 }}>
        <input
          id="ask-pilgrim-input"
          type="text"
          className="ask-input-field"
          placeholder="Type your question here..."
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          disabled={isLoading}
          autoComplete="off"
        />
        <button
          type="submit"
          className="ask-send-btn"
          disabled={!inputVal.trim() || isLoading}
          title="Send query to PilgrimAI"
        >
          <Send size={14} />
        </button>
      </form>

      {messages.length > 0 && (
        <div style={{ textAlign: 'center', marginTop: 6 }}>
          <button 
            type="button" 
            onClick={() => setIsFullChatOpen(true)}
            style={{ background: 'none', border: 'none', color: '#D96B24', fontSize: '0.74rem', cursor: 'pointer', fontWeight: 600 }}
          >
            Open Full Chat View ↗
          </button>
        </div>
      )}
    </div>
  );
}
