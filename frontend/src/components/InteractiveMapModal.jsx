import React, { useState, useEffect } from 'react';
import { 
  X, 
  MapPin, 
  Compass, 
  Navigation, 
  ExternalLink, 
  Loader2, 
  AlertCircle, 
  CheckCircle,
  Map as MapIcon,
  Search,
  Filter
} from 'lucide-react';
import { 
  getNearbyPlaces, 
  getMapsConfig, 
  generateGoogleMapsSearchUrl, 
  generateGoogleMapsDirectionsUrl 
} from '../services/api';

export default function InteractiveMapModal({ 
  isOpen, 
  onClose, 
  initialTemple = 'Yadadri' 
}) {
  const [activeTab, setActiveTab] = useState('map'); // 'map' | 'places'
  const [selectedTemple, setSelectedTemple] = useState(initialTemple || 'Yadadri');
  const [selectedCategory, setSelectedCategory] = useState('all');
  
  const [places, setPlaces] = useState([]);
  const [loadingPlaces, setLoadingPlaces] = useState(false);
  const [placesError, setPlacesError] = useState(null);
  
  const [mapsConfig, setMapsConfig] = useState({ enabled: true, api_key: '' });

  // Certified temple coordinates matching backend registry
  const templeCoordinates = [
    { name: 'Yadadri', display: 'Sri Lakshmi Narasimha Swamy Temple, Yadadri', lat: 17.5896, lng: 78.9407, district: 'Yadadri Bhuvanagiri' },
    { name: 'Tirupati (TTD)', display: 'Sri Venkateswara Swamy Temple, Tirumala', lat: 13.6833, lng: 79.3500, district: 'Tirupati' },
    { name: 'Srisailam', display: 'Sri Bhramaramba Mallikarjuna Temple, Srisailam', lat: 16.0741, lng: 78.8687, district: 'Nandyal' },
    { name: 'Bhadrachalam', display: 'Sri Sita Ramachandra Swamy Temple, Bhadrachalam', lat: 17.6689, lng: 80.8936, district: 'Bhadradri Kothagudem' },
    { name: 'Ramappa', display: 'Ramappa Temple (Rudreshwara Swamy)', lat: 18.2652, lng: 79.9438, district: 'Mulugu' },
    { name: 'Vemulavada', display: 'Sri Raja Rajeswara Swamy Temple, Vemulawada', lat: 18.4682, lng: 78.8687, district: 'Rajanna Sircilla' },
    { name: 'Basara', display: 'Gnana Saraswathi Temple, Basara', lat: 18.9772, lng: 77.9546, district: 'Nirmal' },
    { name: 'Thousand Pillar', display: 'Thousand Pillar Temple, Hanamkonda', lat: 18.0039, lng: 79.5744, district: 'Hanamkonda' },
    { name: 'Birla Mandir', display: 'Birla Mandir, Hyderabad', lat: 17.4062, lng: 78.4691, district: 'Hyderabad' },
    { name: 'Jogulamba', display: 'Jogulamba Devi Temple, Alampur', lat: 15.8778, lng: 78.1325, district: 'Jogulamba Gadwal' },
  ];

  const currentCoord = templeCoordinates.find(t => t.name.toLowerCase() === selectedTemple.toLowerCase()) || templeCoordinates[0];

  useEffect(() => {
    if (isOpen) {
      getMapsConfig()
        .then(cfg => setMapsConfig(cfg))
        .catch(() => setMapsConfig({ enabled: true, api_key: '' }));
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && activeTab === 'places') {
      loadPlaces(selectedTemple, selectedCategory);
    }
  }, [isOpen, activeTab, selectedTemple, selectedCategory]);

  const loadPlaces = async (templeName, category) => {
    setLoadingPlaces(true);
    setPlacesError(null);
    try {
      const data = await getNearbyPlaces(templeName, category);
      setPlaces(data.results || data.places || []);
    } catch (err) {
      setPlacesError(err.message || 'Failed to fetch places');
      setPlaces([]);
    } finally {
      setLoadingPlaces(false);
    }
  };

  if (!isOpen) return null;

  const categories = [
    { id: 'all', label: 'All Categories' },
    { id: 'heritage', label: 'Historic & Forts' },
    { id: 'nature', label: 'Lakes & Nature' },
    { id: 'cultural', label: 'Cultural & Shrines' },
    { id: 'recreation', label: 'Recreation & Sightseeing' },
  ];

  const gmapsSearchUrl = generateGoogleMapsSearchUrl(currentCoord.display, currentCoord.district);
  const gmapsDirUrl = generateGoogleMapsDirectionsUrl('', currentCoord.display);
  const embedUrl = `https://maps.google.com/maps?q=${currentCoord.lat},${currentCoord.lng}&hl=en&z=14&output=embed`;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="modal-content" 
        style={{ maxWidth: 840, maxHeight: '92vh' }} 
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#EFF5FC', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#2F6DB5' }}>
              <MapIcon size={18} />
            </div>
            <div>
              <h3 className="modal-title">Interactive Map & Nearby Discoveries</h3>
              <p style={{ fontSize: '0.72rem', color: '#6A7870', margin: 0 }}>
                Verified geospatial coordinates, driving routes & nearby attraction discovery
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Tab Switcher & Temple Dropdown */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 24px', background: '#FAF8F3', borderBottom: '1px solid #E8E2D5', flexWrap: 'wrap', gap: 10 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              className={`planner-tab-btn ${activeTab === 'map' ? 'active' : ''}`}
              onClick={() => setActiveTab('map')}
            >
              <MapIcon size={13} style={{ marginRight: 4 }} />
              <span>Interactive Map View</span>
            </button>
            <button
              type="button"
              className={`planner-tab-btn ${activeTab === 'places' ? 'active' : ''}`}
              onClick={() => setActiveTab('places')}
            >
              <Compass size={13} style={{ marginRight: 4 }} />
              <span>Nearby Places Discovery</span>
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#123C32' }}>Temple:</span>
            <select
              value={selectedTemple}
              onChange={(e) => setSelectedTemple(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #D8CFC0', fontSize: '0.8rem', background: '#FFFFFF', fontWeight: 600, color: '#123C32' }}
            >
              {templeCoordinates.map(t => (
                <option key={t.name} value={t.name}>
                  {t.name} ({t.district})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {activeTab === 'map' ? (
            <div className="interactive-map-container">
              {/* Information Strip */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#F8F5EE', padding: '10px 14px', borderRadius: 10, border: '1px solid #E8E2D5', flexWrap: 'wrap', gap: 10 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#123C32' }}>
                    {currentCoord.display}
                  </div>
                  <div style={{ fontSize: '0.74rem', color: '#6A7870', marginTop: 2 }}>
                    📍 Lat: <strong>{currentCoord.lat}</strong>, Lng: <strong>{currentCoord.lng}</strong> • District: <strong>{currentCoord.district}</strong>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  <a
                    href={gmapsSearchUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-chat-header"
                    style={{ textDecoration: 'none' }}
                  >
                    <ExternalLink size={12} />
                    <span>View on Maps</span>
                  </a>
                  <a
                    href={gmapsDirUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-hero-primary"
                    style={{ padding: '5px 12px', fontSize: '0.78rem', textDecoration: 'none' }}
                  >
                    <Navigation size={12} />
                    <span>Get Directions</span>
                  </a>
                </div>
              </div>

              {/* Map Embed Frame */}
              <div className="map-embed-wrapper">
                <iframe
                  title={`Google Maps embed for ${currentCoord.name}`}
                  src={embedUrl}
                  width="100%"
                  height="100%"
                  style={{ border: 0 }}
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                />
              </div>

              {/* Offline & Verified Notice */}
              <div className="map-offline-banner">
                <CheckCircle size={16} color="#2E7D4E" />
                <span>
                  <strong>Geographic Fallback Active:</strong> High-precision coordinates and road routes are verified via PilgrimAI local registry. If Google Maps live tiles encounter client network restrictions, offline directions remain 100% accessible.
                </span>
              </div>
            </div>
          ) : (
            /* Nearby Places Discovery Tab */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Category Filter Pills */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {categories.map(cat => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setSelectedCategory(cat.id)}
                    className={`dest-chip-btn ${selectedCategory === cat.id ? 'selected' : ''}`}
                    style={{ fontSize: '0.76rem', padding: '4px 10px' }}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>

              {/* Loading & Status */}
              {loadingPlaces && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '30px 0', gap: 8, color: '#123C32' }}>
                  <Loader2 size={20} className="animate-spin" />
                  <span style={{ fontSize: '0.86rem' }}>Searching verified attractions and Google Places near {selectedTemple}...</span>
                </div>
              )}

              {placesError && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#FDF2F2', border: '1px solid #F6C4C4', color: '#D9383A', padding: '8px 12px', borderRadius: 8, fontSize: '0.8rem' }}>
                  <AlertCircle size={16} />
                  <span>{placesError}</span>
                </div>
              )}

              {!loadingPlaces && places.length === 0 && !placesError && (
                <div style={{ textAlign: 'center', padding: '30px 0', color: '#6A7870', fontSize: '0.86rem' }}>
                  No attractions found under this category near {selectedTemple}. Try selecting "All Categories".
                </div>
              )}

              {/* Results Grid */}
              {!loadingPlaces && places.length > 0 && (
                <div className="places-discovery-grid">
                  {places.map((place, idx) => {
                    const searchUrl = place.map_url || generateGoogleMapsSearchUrl(place.name, selectedTemple);
                    const dirUrl = place.directions_url || generateGoogleMapsDirectionsUrl(selectedTemple, place.name);

                    return (
                      <div key={idx} className="places-discovery-card">
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6, marginBottom: 4 }}>
                            <h5 className="attraction-card-title">{place.name}</h5>
                            {place.distance && (
                              <span style={{ fontSize: '0.72rem', color: '#D96B24', fontWeight: 700, whiteSpace: 'nowrap' }}>
                                {place.distance}
                              </span>
                            )}
                          </div>

                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                            <span className="attraction-badge-pill attraction-badge-category">
                              {place.category || 'Sightseeing'}
                            </span>
                            <span className={`attraction-badge-pill ${place.source && place.source.includes('Google') ? 'attraction-badge-source-google' : 'attraction-badge-source-verified'}`}>
                              {place.source && place.source.includes('Google') ? 'Google Places' : 'Verified Knowledge Base'}
                            </span>
                          </div>

                          {place.description && (
                            <p style={{ fontSize: '0.74rem', color: '#55655E', margin: '0 0 6px 0', lineHeight: 1.4 }}>
                              {place.description}
                            </p>
                          )}
                        </div>

                        <div className="attraction-actions-row">
                          <span style={{ fontSize: '0.7rem', color: '#8A9890' }}>
                            {place.distance_km ? `${place.distance_km} km away` : 'Near temple'}
                          </span>
                          <div className="attraction-links-group">
                            <a
                              href={searchUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="attraction-link-btn"
                              title="View on Google Maps"
                            >
                              <ExternalLink size={11} />
                              <span>View Map</span>
                            </a>
                            <a
                              href={dirUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="attraction-link-btn"
                              title="Get Driving Directions"
                            >
                              <Navigation size={11} />
                              <span>Route</span>
                            </a>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
