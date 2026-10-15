import React from 'react';
import { X, ShieldCheck, Database, Cpu, Award, MapPin } from 'lucide-react';

export default function AboutModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: 580 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Award size={20} color="#D96B24" />
            <h3 className="modal-title">About PilgrimAI Offline Platform</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p style={{ color: '#3A4841', fontSize: '0.86rem', lineHeight: 1.5 }}>
            <strong>PilgrimAI</strong> is an offline, multi-agent artificial intelligence platform designed to guide pilgrims across the sacred shrines of Telangana and Andhra Pradesh without depending on external cloud APIs or proprietary LLM subscriptions.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            <div style={{ background: '#FAF8F3', border: '1px solid #E8E2D5', borderRadius: 10, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#123C32', fontWeight: 700, fontSize: '0.84rem', marginBottom: 4 }}>
                <Cpu size={16} color="#D96B24" />
                <span>Ollama Qwen2.5</span>
              </div>
              <p style={{ fontSize: '0.74rem', color: '#6A7870' }}>
                Local 1.5B quantized neural language model running entirely on local CPU/GPU hardware.
              </p>
            </div>

            <div style={{ background: '#FAF8F3', border: '1px solid #E8E2D5', borderRadius: 10, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#123C32', fontWeight: 700, fontSize: '0.84rem', marginBottom: 4 }}>
                <Database size={16} color="#2F7C48" />
                <span>Hybrid Qdrant + BM25</span>
              </div>
              <p style={{ fontSize: '0.74rem', color: '#6A7870' }}>
                Dual-retrieval engine merging 4,611 dense vector points with 4,458 BM25 lexical documents via RRF.
              </p>
            </div>

            <div style={{ background: '#FAF8F3', border: '1px solid #E8E2D5', borderRadius: 10, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#123C32', fontWeight: 700, fontSize: '0.84rem', marginBottom: 4 }}>
                <ShieldCheck size={16} color="#2F6DB5" />
                <span>10 Specialist Agents</span>
              </div>
              <p style={{ fontSize: '0.74rem', color: '#6A7870' }}>
                Modular domain specialists for timings, itinerary, comparison, navigation, budget, and weather.
              </p>
            </div>

            <div style={{ background: '#FAF8F3', border: '1px solid #E8E2D5', borderRadius: 10, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#123C32', fontWeight: 700, fontSize: '0.84rem', marginBottom: 4 }}>
                <MapPin size={16} color="#83314F" />
                <span>20 Canonical Temples</span>
              </div>
              <p style={{ fontSize: '0.74rem', color: '#6A7870' }}>
                Curated and verified temple records across Telangana and Andhra Pradesh with exact geo-coordinates.
              </p>
            </div>
          </div>

          <div style={{ background: '#EEF7EF', border: '1px solid #D5EBD7', padding: 10, borderRadius: 8, fontSize: '0.76rem', color: '#2E7D4E' }}>
            ✓ Verified 100% local operation: No external telemetry, no cloud LLM keys required.
          </div>
        </div>
      </div>
    </div>
  );
}
