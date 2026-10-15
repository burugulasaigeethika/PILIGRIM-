import React, { useState, useRef, useEffect } from 'react';
import { 
  X, 
  Sparkles, 
  Send, 
  RotateCcw, 
  Loader2, 
  Volume2, 
  VolumeX, 
  Mic, 
  MicOff,
  Navigation,
  Calendar,
  DollarSign
} from 'lucide-react';
import { useChat } from '../context/ChatContext';
import StructuredCards from './StructuredCards';

export default function TravelAssistantModal({ isOpen, onClose }) {
  const { 
    messages, 
    isLoading, 
    sendMessage, 
    startNewSession 
  } = useChat();

  const [inputVal, setInputVal] = useState('');
  const [selectedLang, setSelectedLang] = useState('en');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        if (inputRef.current) inputRef.current.focus();
      }, 100);
    }
  }, [isOpen]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  if (!isOpen) return null;

  const handleSend = (text) => {
    let q = (text || inputVal).trim();
    if (!q || isLoading) return;

    if (selectedLang === 'te' && !q.toLowerCase().includes('telugu')) {
      q = `Answer in Telugu: ${q}`;
    } else if (selectedLang === 'hi' && !q.toLowerCase().includes('hindi')) {
      q = `Answer in Hindi: ${q}`;
    }

    setInputVal('');
    sendMessage(q);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleSend();
  };

  const handleReadAloud = (text) => {
    if (!window.speechSynthesis) return;

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    if (selectedLang === 'te') utterance.lang = 'te-IN';
    else if (selectedLang === 'hi') utterance.lang = 'hi-IN';
    else utterance.lang = 'en-IN';

    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  const handleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice recognition is not supported in this browser.");
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = selectedLang === 'te' ? 'te-IN' : (selectedLang === 'hi' ? 'hi-IN' : 'en-IN');
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onstart = () => setIsListening(true);
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputVal(transcript);
        setIsListening(false);
        if (inputRef.current) inputRef.current.focus();
      };
      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);

      recognition.start();
    } catch (e) {
      console.error(e);
      setIsListening(false);
    }
  };

  const suggestedQueries = [
    { label: "Yadadri Timings & Sevas", q: "What are the timings and special sevas at Yadadri Temple?" },
    { label: "2-Day Tirupati Plan", q: "Plan a 2 day trip to Tirupati Balaji with a budget of ₹5000" },
    { label: "Ramappa Architecture", q: "Explain the Kakatiya architecture and history of Ramappa Temple" },
    { label: "Route: Hyderabad to Srisailam", q: "How to reach Srisailam from Hyderabad by road and travel duration?" },
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="modal-content full-chat-modal" 
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header" style={{ padding: '14px 24px', background: '#FFFFFF' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: '50%', background: '#FCE6D2', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#D96B24' }}>
              <Sparkles size={18} />
            </div>
            <div>
              <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.2rem', fontWeight: 700, color: '#123C32', margin: 0 }}>
                PilgrimAI Travel Assistant
              </h3>
              <span style={{ fontSize: '0.72rem', color: '#6A7870', fontWeight: 500 }}>
                100% Offline Local RAG • Multi-Turn Conversation
              </span>
            </div>
          </div>

          <div className="chat-header-actions">
            {/* Language Selection */}
            <div style={{ display: 'flex', gap: 4, background: '#F8F5EE', padding: '3px 6px', borderRadius: 9999, border: '1px solid #E8E2D5' }}>
              <button 
                type="button" 
                onClick={() => setSelectedLang('en')}
                style={{ border: 'none', background: selectedLang === 'en' ? '#123C32' : 'transparent', color: selectedLang === 'en' ? '#FFF' : '#4C5952', borderRadius: 9999, padding: '2px 8px', fontSize: '0.7rem', fontWeight: 600, cursor: 'pointer' }}
              >
                EN
              </button>
              <button 
                type="button" 
                onClick={() => setSelectedLang('te')}
                style={{ border: 'none', background: selectedLang === 'te' ? '#123C32' : 'transparent', color: selectedLang === 'te' ? '#FFF' : '#4C5952', borderRadius: 9999, padding: '2px 8px', fontSize: '0.7rem', fontWeight: 600, cursor: 'pointer' }}
              >
                తెలుగు
              </button>
              <button 
                type="button" 
                onClick={() => setSelectedLang('hi')}
                style={{ border: 'none', background: selectedLang === 'hi' ? '#123C32' : 'transparent', color: selectedLang === 'hi' ? '#FFF' : '#4C5952', borderRadius: 9999, padding: '2px 8px', fontSize: '0.7rem', fontWeight: 600, cursor: 'pointer' }}
              >
                हिंदी
              </button>
            </div>

            {/* New Chat Button */}
            <button 
              type="button" 
              className="btn-chat-header"
              onClick={startNewSession}
              title="Start a fresh conversation"
            >
              <RotateCcw size={13} />
              <span>New Chat</span>
            </button>

            {/* Close */}
            <button className="modal-close-btn" onClick={onClose} title="Close Chat">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Messages Body */}
        <div className="full-chat-messages-container" ref={scrollRef}>
          {messages.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: '20px' }}>
              <div style={{ width: 60, height: 60, borderRadius: '50%', background: '#FBE8D8', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#D96B24', marginBottom: 14 }}>
                <Sparkles size={30} />
              </div>
              <h4 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', color: '#123C32', marginBottom: 6 }}>
                Welcome to PilgrimAI Travel Assistant
              </h4>
              <p style={{ fontSize: '0.86rem', color: '#5A6961', maxWidth: 480, lineHeight: 1.5, marginBottom: 20 }}>
                Ask detailed questions regarding darshan timings, pooja ticket prices, step-by-step itineraries, driving routes, weather conditions, or accommodation across 20 sacred temples in Telangana and Andhra Pradesh.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, maxWidth: 580, width: '100%' }}>
                {suggestedQueries.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSend(item.q)}
                    style={{
                      background: '#FFFFFF',
                      border: '1px solid #E4DDD1',
                      borderRadius: 12,
                      padding: '10px 14px',
                      textAlign: 'left',
                      fontSize: '0.78rem',
                      color: '#123C32',
                      cursor: 'pointer',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
                      transition: 'all 0.15s'
                    }}
                  >
                    <div style={{ fontWeight: 700, marginBottom: 2 }}>{item.label}</div>
                    <div style={{ color: '#8A9890', fontSize: '0.72rem' }}>{item.q}</div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div 
                key={idx} 
                className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}
              >
                <div className="chat-msg-header">
                  <div className="chat-msg-badges">
                    {msg.role === 'user' ? (
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#D96B24' }}>You</span>
                    ) : (
                      <>
                        {msg.agentName && (
                          <span className="agent-badge-pill">{msg.agentName}</span>
                        )}
                        {msg.confidence !== null && (
                          <span className="confidence-badge-pill">{msg.confidence}% Confidence</span>
                        )}
                        {msg.latencyMs && (
                          <span className="latency-badge-pill">{msg.latencyMs}ms</span>
                        )}
                      </>
                    )}
                  </div>

                  {msg.role === 'assistant' && (
                    <button 
                      type="button" 
                      className="chat-read-aloud-btn"
                      onClick={() => handleReadAloud(msg.content)}
                      title="Read aloud using speech synthesis"
                    >
                      {isSpeaking ? <VolumeX size={14} color="#D9383A" /> : <Volume2 size={14} />}
                      <span>{isSpeaking ? 'Stop' : 'Listen'}</span>
                    </button>
                  )}
                </div>

                <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.88rem', color: '#1A2420', lineHeight: 1.55 }}>
                  {msg.content}
                </div>

                {msg.metadata && <StructuredCards metadata={msg.metadata} />}

                {msg.sources && msg.sources.length > 0 && (
                  <details className="sources-accordion" style={{ marginTop: 10 }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#4A6356' }}>
                      Verified Grounded Sources ({msg.sources.length})
                    </summary>
                    <ul className="sources-list">
                      {msg.sources.map((s, si) => (
                        <li key={si}>{s}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            ))
          )}

          {isLoading && (
            <div className="chat-bubble-assistant" style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#123C32' }}>
              <Loader2 size={18} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
              <span style={{ fontSize: '0.85rem' }}>Consulting offline multi-agent RAG pipeline...</span>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div style={{ padding: '14px 24px', background: '#FFFFFF', borderTop: '1px solid var(--border-subtle)' }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', alignItems: 'center', background: '#FAF8F2', border: '1px solid var(--border-subtle)', borderRadius: 9999, padding: '4px 6px 4px 14px' }}>
            <button
              type="button"
              onClick={handleVoiceInput}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: isListening ? '#D9383A' : '#8A9890', display: 'flex', alignItems: 'center', marginRight: 8 }}
              title={isListening ? "Listening... click to stop" : "Voice input"}
            >
              {isListening ? <MicOff size={18} /> : <Mic size={18} />}
            </button>

            <input
              ref={inputRef}
              type="text"
              placeholder="Ask about timings, navigation routes, weather, or sevas..."
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              disabled={isLoading}
              style={{ border: 'none', background: 'transparent', outline: 'none', flex: 1, fontSize: '0.88rem', color: '#1A2420' }}
            />

            <button
              type="submit"
              disabled={!inputVal.trim() || isLoading}
              className="btn-hero-primary"
              style={{ padding: '7px 18px', fontSize: '0.84rem' }}
            >
              <span>Ask AI</span>
              <Send size={14} />
            </button>
          </form>

          <div style={{ textAlign: 'center', marginTop: 8, fontSize: '0.7rem', color: '#8A9890' }}>
            <span>⚡ 100% Local RAG + Live Multi-Agent Architecture • Offline Vector & Keyword Grounding</span>
          </div>
        </div>
      </div>
    </div>
  );
}
