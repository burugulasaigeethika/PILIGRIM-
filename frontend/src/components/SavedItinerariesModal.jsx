import React, { useState, useEffect } from 'react';
import { 
  X, 
  FileText, 
  Calendar, 
  Users, 
  Trash2, 
  MessageSquare, 
  Loader2, 
  LogIn,
  CheckCircle,
  AlertCircle
} from 'lucide-react';
import { getSavedItineraries, deleteSavedItinerary } from '../services/api';

export default function SavedItinerariesModal({ 
  isOpen, 
  onClose, 
  onContinueInChat, 
  onOpenAuth 
}) {
  const [itineraries, setItineraries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activePlan, setActivePlan] = useState(null);
  const [actionMsg, setActionMsg] = useState(null);

  const loadData = async () => {
    const token = localStorage.getItem('pilgrim_token');
    if (!token) {
      setItineraries([]);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await getSavedItineraries();
      setItineraries(data.itineraries || []);
    } catch (err) {
      setError(err.message || 'Failed to load saved itineraries.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setActivePlan(null);
      loadData();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const token = localStorage.getItem('pilgrim_token');

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to remove this saved itinerary?")) return;
    try {
      await deleteSavedItinerary(id);
      setItineraries(prev => prev.filter(item => item.itinerary_id !== id));
      setActionMsg("Itinerary deleted successfully.");
      setTimeout(() => setActionMsg(null), 3000);
      if (activePlan?.itinerary_id === id) setActivePlan(null);
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="modal-content" 
        style={{ maxWidth: 680, maxHeight: '88vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: '50%', background: '#FCE6D2', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#D96B24' }}>
              <FileText size={18} />
            </div>
            <div>
              <h3 className="modal-title">My Saved Pilgrimage Plans</h3>
              <span style={{ fontSize: '0.72rem', color: '#6A7870' }}>
                Saved itineraries and verified budget breakdowns in your profile
              </span>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {actionMsg && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#EEF7EF', border: '1px solid #D5EBD7', color: '#2E7D4E', padding: '6px 12px', borderRadius: 8, fontSize: '0.78rem', marginBottom: 12 }}>
              <CheckCircle size={14} />
              <span>{actionMsg}</span>
            </div>
          )}

          {!token ? (
            <div style={{ textAlign: 'center', padding: '36px 20px' }}>
              <LogIn size={40} color="#D96B24" style={{ marginBottom: 12 }} />
              <h4 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.15rem', color: '#123C32', marginBottom: 6 }}>
                Sign In to View Your Saved Itineraries
              </h4>
              <p style={{ fontSize: '0.84rem', color: '#6A7870', maxWidth: 360, margin: '0 auto 16px', lineHeight: 1.5 }}>
                Your saved pilgrimage schedules are securely stored in your personal profile. Sign in or create an account to access them anytime.
              </p>
              <button 
                type="button" 
                className="btn-hero-primary"
                onClick={() => {
                  onClose();
                  if (onOpenAuth) onOpenAuth();
                }}
              >
                Sign In / Register
              </button>
            </div>
          ) : activePlan ? (
            /* Detailed view of chosen plan */
            <div>
              <button
                type="button"
                onClick={() => setActivePlan(null)}
                style={{ background: 'none', border: 'none', color: '#D96B24', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', marginBottom: 12 }}
              >
                ← Back to All Saved Plans
              </button>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
                <div>
                  <h4 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.2rem', color: '#123C32', margin: 0 }}>
                    {activePlan.title || 'Saved Pilgrimage Itinerary'}
                  </h4>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                    {(activePlan.destinations || []).map((d, di) => (
                      <span key={di} style={{ background: '#FAF8F2', border: '1px solid #E8E2D5', padding: '2px 8px', borderRadius: 9999, fontSize: '0.72rem', color: '#123C32', fontWeight: 600 }}>
                        {d}
                      </span>
                    ))}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    if (onContinueInChat) {
                      onContinueInChat(
                        `Here is my saved itinerary for ${activePlan.destinations.join(' and ')}. Please provide travel and darshan advice.`,
                        { answer: activePlan.itinerary_text }
                      );
                    }
                  }}
                  className="btn-hero-primary"
                  style={{ padding: '6px 14px', fontSize: '0.78rem' }}
                >
                  <MessageSquare size={13} />
                  <span>Discuss in Chat</span>
                </button>
              </div>

              <div style={{ background: '#FAF8F3', border: '1px solid #E8E2D5', borderRadius: 12, padding: 18, maxHeight: 380, overflowY: 'auto' }}>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', color: '#1A2420', lineHeight: 1.6 }}>
                  {activePlan.itinerary_text}
                </div>
              </div>
            </div>
          ) : loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px', gap: 10, color: '#123C32' }}>
              <Loader2 size={22} className="animate-spin" />
              <span>Loading saved itineraries from profile...</span>
            </div>
          ) : error ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#D9383A', background: '#FDF2F2', padding: 12, borderRadius: 8, fontSize: '0.84rem' }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          ) : itineraries.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#6A7870' }}>
              <FileText size={38} color="#C4B8A6" style={{ marginBottom: 12 }} />
              <h4 style={{ color: '#123C32', fontSize: '1rem', marginBottom: 4 }}>No Saved Itineraries Yet</h4>
              <p style={{ fontSize: '0.82rem', maxWidth: 360, margin: '0 auto' }}>
                Use the "Trip Planner" on your dashboard to customize a multi-temple pilgrimage schedule and save it here.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 420, overflowY: 'auto' }}>
              {itineraries.map((item) => (
                <div key={item.itinerary_id} className="saved-itin-card">
                  <div>
                    <h5 style={{ fontSize: '0.92rem', color: '#123C32', fontWeight: 700, marginBottom: 4 }}>
                      {item.title}
                    </h5>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
                      {(item.destinations || []).map((d, di) => (
                        <span key={di} style={{ background: '#FAF8F2', border: '1px solid #E8E2D5', padding: '1px 6px', borderRadius: 4, fontSize: '0.68rem', color: '#4C5952' }}>
                          {d}
                        </span>
                      ))}
                    </div>
                    <div style={{ display: 'flex', gap: 12, fontSize: '0.74rem', color: '#8A9890' }}>
                      <span>📅 {item.duration_days || 1} Day(s)</span>
                      <span>👥 {item.pax || 1} Pilgrim(s)</span>
                      {item.budget_limit && <span>💰 ₹{Number(item.budget_limit).toLocaleString()}</span>}
                    </div>
                  </div>

                  <div className="saved-itin-actions">
                    <button 
                      type="button" 
                      className="btn-itin-action view"
                      onClick={() => setActivePlan(item)}
                    >
                      View
                    </button>
                    <button 
                      type="button" 
                      className="btn-itin-action delete"
                      onClick={() => handleDelete(item.itinerary_id)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
