import React from 'react';
import { Compass, Calendar, ArrowRight } from 'lucide-react';

export default function HeroBanner({ onExploreTemples, onPlanTrip }) {
  return (
    <div className="hero-banner">
      <div className="hero-left">
        <span className="hero-tag">WELCOME TO PILGRIMAI</span>
        <h2 className="hero-title">
          Discover Temples.<br />
          Plan Meaningful Journeys.
        </h2>
        <p className="hero-description">
          Your AI-powered companion for temple exploration, spiritual travel and personalized itineraries across India.
        </p>

        <div className="hero-actions">
          <button className="btn-hero-primary" onClick={onExploreTemples}>
            <Compass size={17} />
            <span>Explore Temples</span>
            <ArrowRight size={15} />
          </button>

          <button className="btn-hero-secondary" onClick={onPlanTrip}>
            <Calendar size={17} />
            <span>Plan Your Trip</span>
          </button>
        </div>
      </div>

      <div className="hero-right">
        <img 
          src="/static/assets/hero_temple.png" 
          alt="Sacred Temple Architecture" 
          className="hero-temple-bg"
          onError={(e) => {
            e.target.src = '/static/assets/hero_banner.jpg';
          }}
        />
        <div className="hero-quote-badge">
          <p className="hero-quote-text">
            “Temples are not just places, they are journeys within.”
          </p>
          <div className="hero-quote-ornament">✧</div>
        </div>
      </div>
    </div>
  );
}
