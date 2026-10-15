import React, { useState } from 'react';
import { Landmark, MapPin, Heart, ArrowRight } from 'lucide-react';

export default function PopularTemples({ 
  onSelectTemple, 
  onViewAll,
  onOpenMap
}) {
  const [favorites, setFavorites] = useState({});

  const toggleFavorite = (e, templeId) => {
    e.stopPropagation();
    setFavorites(prev => ({ ...prev, [templeId]: !prev[templeId] }));
  };

  // Canonical featured temples from verified project dataset
  const featuredTemples = [
    {
      id: 'yadadri',
      name: 'Yadadri Temple',
      state: 'Telangana',
      district: 'Yadadri Bhuvanagiri',
      image: '/static/assets/yadadri_photo.jpg',
      fallbackImage: '/static/assets/yadadri.jpg',
      description: 'A renowned temple dedicated to Lord Lakshmi Narasimha, known for its magnificent architecture.',
      deity: 'Lord Sri Lakshmi Narasimha Swamy',
      timings: '04:00 AM - 09:45 PM',
      bestTime: 'October to March'
    },
    {
      id: 'tirupati',
      name: 'Tirupati Balaji',
      state: 'Andhra Pradesh',
      district: 'Tirupati',
      image: '/static/assets/tirupati_photo.jpg',
      fallbackImage: '/static/assets/tirupati.jpg',
      description: 'One of the most visited temples in the world, devoted to Lord Venkateswara.',
      deity: 'Lord Sri Venkateswara Swamy (Balaji)',
      timings: '03:00 AM - 01:30 AM (Next Day)',
      bestTime: 'September to February'
    },
    {
      id: 'ramappa',
      name: 'Ramappa Temple',
      state: 'Telangana',
      district: 'Mulugu',
      image: '/static/assets/ramappa_photo.jpg',
      fallbackImage: '/static/assets/ramappa.jpg',
      description: 'A UNESCO World Heritage Site known for its exquisite Kakatiya architecture.',
      deity: 'Ramalingeswara Swamy (Lord Shiva)',
      timings: '06:00 AM - 06:00 PM',
      bestTime: 'October to March'
    },
    {
      id: 'bhadrachalam',
      name: 'Bhadrachalam Temple',
      state: 'Telangana',
      district: 'Bhadradri Kothagudem',
      image: '/static/assets/bhadrachalam_photo.jpg',
      fallbackImage: '/static/assets/bhadrachalam.jpg',
      description: 'A sacred temple dedicated to Lord Rama, located on the banks of the Godavari.',
      deity: 'Lord Sri Sita Ramachandra Swamy',
      timings: '04:30 AM - 09:00 PM',
      bestTime: 'November to February'
    }
  ];

  return (
    <section className="popular-temples-section">
      <div className="section-header-row">
        <div className="section-title-wrap">
          <Landmark className="section-icon" />
          <h3 className="section-title">Popular Temples</h3>
        </div>
        <button className="view-all-link" onClick={onViewAll}>
          <span>View All</span>
          <ArrowRight size={14} />
        </button>
      </div>

      <div className="temples-cards-grid">
        {featuredTemples.map((temple) => {
          const isFavorited = !!favorites[temple.id];
          return (
            <div 
              key={temple.id} 
              className="temple-card"
              onClick={() => onSelectTemple(temple)}
            >
              <div className="temple-image-wrap">
                <img 
                  src={temple.image} 
                  alt={temple.name} 
                  className="temple-image"
                  onError={(e) => {
                    e.target.src = temple.fallbackImage;
                  }}
                />
                <button 
                  className={`favorite-btn ${isFavorited ? 'favorited' : ''}`}
                  onClick={(e) => toggleFavorite(e, temple.id)}
                  title={isFavorited ? "Remove from Favorites" : "Add to Favorites"}
                >
                  <Heart size={14} fill={isFavorited ? "currentColor" : "none"} />
                </button>
              </div>

              <div className="temple-body">
                <div>
                  <h4 className="temple-title">{temple.name}</h4>
                  <div className="temple-location">
                    <MapPin className="temple-location-icon" />
                    <span>{temple.state}</span>
                  </div>
                  <p className="temple-description">{temple.description}</p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, marginTop: 10 }}>
                  <button 
                    type="button"
                    className="btn-chat-header"
                    style={{ padding: '4px 8px', fontSize: '0.72rem' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onOpenMap) onOpenMap(temple.name);
                    }}
                    title="View temple location & nearby places on Interactive Map"
                  >
                    <MapPin size={12} color="#D96B24" />
                    <span>Map</span>
                  </button>

                  <button 
                    className="btn-temple-details"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectTemple(temple);
                    }}
                  >
                    <span>View Details</span>
                    <ArrowRight size={12} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
