import React from 'react';
import { CloudSun, Navigation, DollarSign, Calendar, MapPin, Clock, ExternalLink, Compass } from 'lucide-react';
import { generateGoogleMapsSearchUrl, generateGoogleMapsDirectionsUrl } from '../services/api';

export default function StructuredCards({ metadata }) {
  if (!metadata || typeof metadata !== 'object') return null;

  const curWeather = metadata.current_weather;
  const hasWeather = Boolean(curWeather && (curWeather.temperature !== undefined || curWeather.condition));
  
  const hasRoute = Boolean(metadata.distance_km !== undefined || (metadata.route_legs && metadata.route_legs.length > 0));
  
  const totalBudget = metadata.calculated_total || metadata.budget;
  const hasBudget = Boolean(totalBudget && (totalBudget.min !== undefined || totalBudget.total !== undefined));

  const placesList = metadata.places || metadata.results || metadata.nearby_places || metadata.attractions || metadata.nearby_attractions;
  const hasPlaces = Boolean(placesList && Array.isArray(placesList) && placesList.length > 0);

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
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Navigation size={16} color="#D96B24" />
              <span style={{ fontWeight: 700, fontSize: '0.84rem', color: '#123C32' }}>
                Travel & Road Route
              </span>
            </div>
            {metadata.origin && metadata.destination && (
              <a
                href={generateGoogleMapsDirectionsUrl(metadata.origin, metadata.destination)}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: '0.72rem', color: '#D96B24', display: 'inline-flex', alignItems: 'center', gap: 3, fontWeight: 600, textDecoration: 'none' }}
              >
                <span>Live Route</span>
                <ExternalLink size={11} />
              </a>
            )}
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
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#6A7870', marginTop: 3 }}>
                  <span>{leg.origin || leg.from} ➔ {leg.destination || leg.to}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>{leg.distance_km ? `${leg.distance_km} km` : ''}</span>
                    <a
                      href={generateGoogleMapsDirectionsUrl(leg.origin || leg.from, leg.destination || leg.to)}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Open leg in Google Maps"
                      style={{ color: '#D96B24' }}
                    >
                      <ExternalLink size={10} />
                    </a>
                  </div>
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

      {/* Nearby Places / Discoveries Card */}
      {hasPlaces && (
        <div className="structured-card" style={{ background: '#FAF8F3', borderColor: '#E5DDCF' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <Compass size={16} color="#D96B24" />
            <span style={{ fontWeight: 700, fontSize: '0.84rem', color: '#123C32' }}>
              Nearby Attractions & Discoveries ({placesList.length})
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {placesList.slice(0, 5).map((p, pi) => {
              const name = p.name || p.display_name;
              const cat = p.category || p.type;
              const searchUrl = p.map_url || generateGoogleMapsSearchUrl(name, metadata.display_name || '');
              const dirUrl = p.directions_url || generateGoogleMapsDirectionsUrl(metadata.display_name || '', name);

              return (
                <div key={pi} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#FFFFFF', padding: '6px 10px', borderRadius: 8, border: '1px solid #ECE4D8', fontSize: '0.76rem' }}>
                  <div>
                    <div style={{ fontWeight: 600, color: '#123C32' }}>{name}</div>
                    <div style={{ display: 'flex', gap: 6, fontSize: '0.68rem', color: '#8A9890', marginTop: 1 }}>
                      {cat && <span>{cat}</span>}
                      {p.distance && <span>• {p.distance}</span>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <a
                      href={searchUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="attraction-link-btn"
                      title="View on Google Maps"
                    >
                      <ExternalLink size={10} />
                      <span>Map</span>
                    </a>
                    <a
                      href={dirUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="attraction-link-btn"
                      title="Get Directions"
                    >
                      <Navigation size={10} />
                      <span>Route</span>
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
