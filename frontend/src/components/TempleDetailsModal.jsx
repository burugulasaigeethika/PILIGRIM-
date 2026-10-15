import React from 'react';
import { X, MapPin, Clock, Calendar, Sparkles } from 'lucide-react';

export default function TempleDetailsModal({ temple, onClose, onAskAboutTemple }) {
  if (!temple) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">{temple.name}</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {temple.image && (
            <div style={{ height: 180, overflow: 'hidden', borderRadius: 12, marginBottom: 16 }}>
              <img 
                src={temple.image} 
                alt={temple.name} 
                style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                onError={(e) => {
                  if (temple.fallbackImage) e.target.src = temple.fallbackImage;
                }}
              />
            </div>
          )}

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#F8F4EC', padding: '4px 10px', borderRadius: 9999, fontSize: '0.8rem', color: '#D96B24', fontWeight: 600 }}>
              <MapPin size={14} />
              {temple.district ? `${temple.district}, ` : ''}{temple.state}
            </span>
            {temple.timings && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#EFF6F0', padding: '4px 10px', borderRadius: 9999, fontSize: '0.8rem', color: '#2E7D4E', fontWeight: 600 }}>
                <Clock size={14} />
                {temple.timings}
              </span>
            )}
            {temple.bestTime && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#F5F0FC', padding: '4px 10px', borderRadius: 9999, fontSize: '0.8rem', color: '#6C44B5', fontWeight: 600 }}>
                <Calendar size={14} />
                {temple.bestTime}
              </span>
            )}
          </div>

          <div style={{ marginBottom: 14 }}>
            <h4 style={{ fontSize: '0.92rem', color: '#123C32', marginBottom: 4 }}>Presiding Deity</h4>
            <p style={{ color: '#4A5568' }}>{temple.deity || 'Sacred Divine Deity'}</p>
          </div>

          <div style={{ marginBottom: 14 }}>
            <h4 style={{ fontSize: '0.92rem', color: '#123C32', marginBottom: 4 }}>Overview & Significance</h4>
            <p style={{ color: '#4A5568', lineHeight: 1.5 }}>{temple.description}</p>
          </div>

          <div style={{ background: '#FAF8F3', border: '1px solid #ECE7DD', padding: 12, borderRadius: 10, fontSize: '0.8rem', color: '#55655E' }}>
            <strong>Pilgrimage Guidelines:</strong> Traditional dress code is recommended. Darshan timings may vary on festival days and Ekadashi/Pournami.
          </div>
        </div>

        <div className="modal-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(temple.name + (temple.district ? ' ' + temple.district : '') + ' ' + temple.state)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-chat-header"
              style={{ textDecoration: 'none' }}
              title="Open location on Google Maps"
            >
              <MapPin size={13} color="#D96B24" />
              <span>View on Maps</span>
            </a>
            <a
              href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(temple.name + (temple.district ? ' ' + temple.district : '') + ' ' + temple.state)}&travelmode=driving`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-chat-header"
              style={{ textDecoration: 'none' }}
              title="Get driving directions on Google Maps"
            >
              <span>Get Directions</span>
            </a>
          </div>

          <button 
            className="btn-hero-primary" 
            style={{ fontSize: '0.82rem', padding: '8px 16px' }}
            onClick={() => {
              onClose();
              if (onAskAboutTemple) onAskAboutTemple(`Tell me detailed timings, rituals, and travel advice for ${temple.name}`);
            }}
          >
            <Sparkles size={14} />
            <span>Ask PilgrimAI</span>
          </button>
        </div>
      </div>
    </div>
  );
}
