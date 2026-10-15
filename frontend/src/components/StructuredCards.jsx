import React from 'react';
import { CloudSun, Navigation, DollarSign, Calendar, MapPin, Clock } from 'lucide-react';

export default function StructuredCards({ metadata }) {
  if (!metadata || typeof metadata !== 'object') return null;

  const curWeather = metadata.current_weather;
  const hasWeather = Boolean(curWeather && (curWeather.temperature !== undefined || curWeather.condition));
  
  const hasRoute = Boolean(metadata.distance_km !== undefined || (metadata.route_legs && metadata.route_legs.length > 0));
  
  const totalBudget = metadata.calculated_total || metadata.budget;
  const hasBudget = Boolean(totalBudget && (totalBudget.min !== undefined || totalBudget.total !== undefined));

  return (
    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Weather Card */}
      {hasWeather && (
        <div className="structured-card weather-card-react">
          <div className="weather-card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <CloudSun size={18} color="#2F7C48" />
              <span style={{ fontWeight: 700, fontSize: '0.84rem', color: '#123C32' }}>
                {metadata.display_name || metadata.location || 'Temple Weather'}
              </span>
            </div>
            <span className="weather-temp-badge">
              {curWeather.temperature !== undefined ? `${curWeather.temperature}°C` : ''}
            </span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#2F7C48', fontWeight: 600 }}>
            {curWeather.condition || 'Live Observation'}
          </div>
          <div className="weather-details-grid">
            <span>💧 Humidity: {curWeather.relative_humidity !== undefined ? `${curWeather.relative_humidity}%` : '--'}</span>
            <span>💨 Wind: {curWeather.wind_speed !== undefined ? `${curWeather.wind_speed} km/h` : '--'}</span>
            <span>🌧 Rain: {curWeather.precipitation !== undefined ? `${curWeather.precipitation} mm` : '--'}</span>
          </div>
        </div>
      )}

      {/* Navigation & Route Card */}
      {hasRoute && (
        <div className="structured-card nav-card-react">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <Navigation size={16} color="#D96B24" />
            <span style={{ fontWeight: 700, fontSize: '0.84rem', color: '#123C32' }}>
              Travel & Road Route
            </span>
          </div>
          <div className="nav-route-row">
            <span>Total Distance:</span>
            <span>{metadata.distance_km || metadata.total_distance_km || '--'} km</span>
          </div>
          {metadata.duration_minutes && (
            <div className="nav-route-row">
              <span>Estimated Travel Time:</span>
              <span>{Math.round(metadata.duration_minutes)} mins</span>
            </div>
          )}
          {metadata.route_legs && metadata.route_legs.length > 0 && (
            <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px dashed #EADDCF', fontSize: '0.74rem' }}>
              <span style={{ fontWeight: 600, color: '#55655E' }}>Route Legs:</span>
              {metadata.route_legs.map((leg, idx) => (
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', color: '#6A7870', marginTop: 2 }}>
                  <span>{leg.origin || leg.from} ➔ {leg.destination || leg.to}</span>
                  <span>{leg.distance_km ? `${leg.distance_km} km` : ''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Budget Breakdown Card */}
      {hasBudget && (
        <div className="structured-card budget-card-react">
          <div className="budget-total-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <DollarSign size={16} color="#925C26" />
              <span style={{ fontWeight: 700, fontSize: '0.84rem', color: '#123C32' }}>
                Estimated Pilgrimage Budget
              </span>
            </div>
            <span className="budget-total-val">
              {totalBudget.min !== undefined && totalBudget.max !== undefined
                ? (totalBudget.min === totalBudget.max ? `₹${totalBudget.min.toLocaleString()}` : `₹${totalBudget.min.toLocaleString()} - ₹${totalBudget.max.toLocaleString()}`)
                : `₹${(totalBudget.total || 0).toLocaleString()}`}
            </span>
          </div>
          {totalBudget.categories && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6, fontSize: '0.74rem', color: '#5C4A3A' }}>
              {Object.entries(totalBudget.categories).map(([k, v], ki) => (
                <div key={ki} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ textTransform: 'capitalize' }}>{k}:</span>
                  <span style={{ fontWeight: 600 }}>₹{typeof v === 'number' ? v.toLocaleString() : (v?.min || v?.total || JSON.stringify(v))}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
