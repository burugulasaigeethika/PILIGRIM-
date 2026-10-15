import React, { useState, useEffect } from 'react';
import { X, Clock, MessageSquare, ArrowRight, Loader2, UserCheck } from 'lucide-react';

export default function ChatHistoryModal({ isOpen, onClose, user, onOpenAuth }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeSession, setActiveSession] = useState(null);
  const [sessionMessages, setSessionMessages] = useState([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const token = localStorage.getItem('pilgrim_token');
      if (token) {
        setLoading(true);
        fetch('/api/chat/history', {
          headers: { Authorization: `Bearer ${token}` }
        })
          .then((res) => res.ok ? res.json() : [])
          .then((data) => setSessions(data))
          .catch(() => setSessions([]))
          .finally(() => setLoading(false));
      } else {
        setSessions([]);
      }
    }
  }, [isOpen, user]);

  const loadSession = async (sess) => {
    setActiveSession(sess);
    setLoadingMessages(true);
    const token = localStorage.getItem('pilgrim_token');
    try {
      const res = await fetch(`/api/chat/history/${encodeURIComponent(sess.session_id)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const msgs = await res.json();
        setSessionMessages(msgs);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingMessages(false);
    }
  };

  if (!isOpen) return null;

  const token = localStorage.getItem('pilgrim_token');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: 640 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Clock size={20} color="#6C44B5" />
            <h3 className="modal-title">Past Pilgrimage Conversations</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {!token ? (
            <div style={{ textAlign: 'center', padding: '30px 20px' }}>
              <UserCheck size={40} color="#6C44B5" style={{ marginBottom: 12 }} />
              <h4 style={{ fontSize: '1rem', color: '#123C32', marginBottom: 6 }}>Sign In to Sync Chat History</h4>
              <p style={{ fontSize: '0.84rem', color: '#6A7870', maxWidth: 360, margin: '0 auto 16px' }}>
                Chat histories are securely isolated per user account. Sign in to review your past pilgrimage itineraries and queries.
              </p>
              <button 
                className="btn-hero-primary" 
                style={{ fontSize: '0.84rem' }}
                onClick={() => {
                  onClose();
                  onOpenAuth();
                }}
              >
                Sign In or Create Account
              </button>
            </div>
          ) : activeSession ? (
            <div>
              <button 
                onClick={() => setActiveSession(null)}
                style={{ background: 'none', border: 'none', color: '#D96B24', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', marginBottom: 12 }}
              >
                ← Back to all conversations
              </button>
              <h4 style={{ fontSize: '0.96rem', color: '#123C32', marginBottom: 12 }}>{activeSession.title}</h4>

              {loadingMessages ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
                  <Loader2 size={20} className="animate-spin" />
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 350, overflowY: 'auto' }}>
                  {sessionMessages.map((msg, i) => (
                    <div 
                      key={i} 
                      style={{
                        padding: 10,
                        borderRadius: 10,
                        background: msg.role === 'user' ? '#F4F0E6' : '#EFF7F1',
                        border: `1px solid ${msg.role === 'user' ? '#E5DDCB' : '#D2EAD7'}`,
                        fontSize: '0.82rem',
                        alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                        maxWidth: '90%'
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: '0.72rem', color: msg.role === 'user' ? '#6C5A48' : '#123C32', marginBottom: 3 }}>
                        {msg.role === 'user' ? 'You' : (msg.agent_name || 'PilgrimAI Agent')}
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 30, gap: 8 }}>
              <Loader2 size={20} className="animate-spin" />
              <span>Loading saved sessions...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px 20px', color: '#6A7870' }}>
              <MessageSquare size={36} color="#8A9890" style={{ marginBottom: 10 }} />
              <p>No past chat sessions found. Start a conversation on the dashboard!</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 380, overflowY: 'auto' }}>
              {sessions.map((sess) => (
                <div 
                  key={sess.session_id}
                  onClick={() => loadSession(sess)}
                  style={{
                    background: '#FAF8F3',
                    border: '1px solid #E8E2D5',
                    borderRadius: 10,
                    padding: 12,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                >
                  <div>
                    <h5 style={{ fontSize: '0.88rem', color: '#123C32', fontWeight: 600 }}>{sess.title}</h5>
                    <span style={{ fontSize: '0.72rem', color: '#8A9890' }}>
                      {new Date(sess.updated_at).toLocaleString()}
                    </span>
                  </div>
                  <ArrowRight size={14} color="#D96B24" />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
