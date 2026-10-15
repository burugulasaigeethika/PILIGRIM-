import React, { useState, useEffect } from 'react';
import { X, Landmark, MapPin, Search, ArrowRight, Loader2 } from 'lucide-react';
import { getTemples } from '../services/api';

export default function ExploreTemplesModal({ isOpen, onClose, onSelectTemple }) {
  const [temples, setTemples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterState, setFilterState] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      getTemples()
        .then((data) => {
          if (Array.isArray(data)) {
            setTemples(data);
          }
        })
        .catch((err) => {
          console.error("Failed to load canonical temples:", err);
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const filtered = temples.filter((t) => {
    const nameMatch = (t.display_name || t.canonical_name || '')
      .toLowerCase()
      .includes(searchTerm.toLowerCase()) ||
      (t.district || '').toLowerCase().includes(searchTerm.toLowerCase());
    if (!nameMatch) return false;
    if (filterState === 'ALL') return true;
    return (t.state || '').toUpperCase().includes(filterState);
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: 780 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Landmark size={22} color="#D96B24" />
            <h3 className="modal-title">Canonical Temples Directory ({temples.length})</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Search & State Filter */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', background: '#F8F5EE', border: '1px solid #E8E2D5', borderRadius: 9999, padding: '4px 12px', flex: 1 }}>
              <Search size={16} color="#8A9890" style={{ marginRight: 8 }} />
              <input 
                type="text" 
                placeholder="Search temples by name or district..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ border: 'none', background: 'transparent', outline: 'none', width: '100%', fontSize: '0.84rem' }}
              />
            </div>
            <select 
              value={filterState} 
              onChange={(e) => setFilterState(e.target.value)}
              style={{ background: '#F8F5EE', border: '1px solid #E8E2D5', borderRadius: 9999, padding: '4px 14px', fontSize: '0.82rem', color: '#123C32', outline: 'none', fontWeight: 600 }}
            >
              <option value="ALL">All States</option>
              <option value="TELANGANA">Telangana</option>
              <option value="ANDHRA">Andhra Pradesh</option>
            </select>
          </div>

          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, gap: 8, color: '#123C32' }}>
              <Loader2 size={24} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
              <span>Loading canonical temples from database...</span>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, maxHeight: 420, overflowY: 'auto' }}>
              {filtered.map((t, idx) => (
                <div 
                  key={idx}
                  style={{
                    background: '#FAF8F3',
                    border: '1px solid #E8E2D5',
                    borderRadius: 12,
                    padding: 12,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                  onClick={() => {
                    onClose();
                    onSelectTemple({
                      id: t.canonical_name,
                      name: t.display_name,
                      state: t.state,
                      district: t.district,
                      description: `Canonical pilgrimage shrine in ${t.district}, ${t.state}. Latitude: ${t.latitude}, Longitude: ${t.longitude}.`,
                    });
                  }}
                >
                  <div>
                    <h4 style={{ fontSize: '0.92rem', color: '#123C32', fontWeight: 700 }}>{t.display_name}</h4>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#D96B24', fontSize: '0.74rem', marginTop: 4 }}>
                      <MapPin size={12} />
                      <span>{t.district}, {t.state}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 6, borderTop: '1px dashed #E2DDD1', fontSize: '0.72rem', color: '#6A7870' }}>
                    <span>Verified: {t.verification_status || 'Canonical'}</span>
                    <span style={{ color: '#D96B24', display: 'flex', alignItems: 'center', gap: 2, fontWeight: 600 }}>
                      Details <ArrowRight size={11} />
                    </span>
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
