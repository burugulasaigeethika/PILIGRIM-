import React from 'react';
import { Landmark, MapPin, Users, Award } from 'lucide-react';

export default function StatisticsStrip() {
  const stats = [
    {
      id: 'temples',
      number: '20+',
      label: 'Canonical Temples',
      icon: Landmark,
      colorClass: 'stat-icon-orange',
    },
    {
      id: 'states',
      number: '2',
      label: 'States (TS & AP)',
      icon: MapPin,
      colorClass: 'stat-icon-brown',
    },
    {
      id: 'agents',
      number: '10',
      label: 'Specialist Agents',
      icon: Users,
      colorClass: 'stat-icon-green',
    },
    {
      id: 'rag',
      number: '100%',
      label: 'Offline RAG & Embeddings',
      icon: Award,
      colorClass: 'stat-icon-badge',
    },
  ];

  return (
    <div className="statistics-strip">
      {stats.map((st) => {
        const Icon = st.icon;
        return (
          <div key={st.id} className="stat-item">
            <div className={`stat-icon-wrap ${st.colorClass}`}>
              <Icon size={22} />
            </div>
            <div className="stat-info">
              <span className="stat-number">{st.number}</span>
              <span className="stat-label">{st.label}</span>
            </div>
          </div>
        );
      })}

      <img 
        src="/static/assets/landscape_corner.png" 
        alt="Pilgrim Landscape" 
        className="stats-landscape-bg"
        onError={(e) => {
          e.target.style.display = 'none';
        }}
      />
    </div>
  );
}
