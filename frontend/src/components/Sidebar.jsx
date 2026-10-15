import React from 'react';
import { 
  Home, 
  Landmark, 
  MessageSquare, 
  Calendar, 
  Clock, 
  FileText, 
  Info,
  MapPin
} from 'lucide-react';

export default function Sidebar({ 
  activeNav, 
  setActiveNav, 
  onOpenAssistant,
  onOpenTripPlanner, 
  onOpenSavedItineraries,
  onOpenChatHistory, 
  onOpenAbout,
  onOpenExplore,
  onOpenMap
}) {
  const navItems = [
    { 
      id: 'dashboard', 
      label: 'Dashboard', 
      icon: Home, 
      action: () => setActiveNav('dashboard') 
    },
    { 
      id: 'explore', 
      label: 'Explore Temples', 
      icon: Landmark, 
      action: onOpenExplore 
    },
    { 
      id: 'map', 
      label: 'Map & Places', 
      icon: MapPin, 
      action: onOpenMap 
    },
    { 
      id: 'assistant', 
      label: 'AI Travel Assistant', 
      icon: MessageSquare, 
      action: onOpenAssistant 
    },
    { 
      id: 'planner', 
      label: 'Trip Planner', 
      icon: Calendar, 
      action: onOpenTripPlanner 
    },
    { 
      id: 'history', 
      label: 'Chat History', 
      icon: Clock, 
      action: onOpenChatHistory 
    },
    { 
      id: 'itineraries', 
      label: 'My Itineraries', 
      icon: FileText, 
      action: onOpenSavedItineraries 
    },
    { 
      id: 'about', 
      label: 'About', 
      icon: Info, 
      action: onOpenAbout 
    },
  ];

  return (
    <aside className="sidebar">
      <div>
        {/* Brand Section */}
        <div className="brand-section">
          <img 
            src="/static/assets/logo_icon.png" 
            alt="PilgrimAI Gopuram" 
            className="brand-logo-icon" 
            onError={(e) => {
              e.target.style.display = 'none';
            }}
          />
          <div className="brand-text-container">
            <h1 className="brand-name">
              Pilgrim<span className="ai-accent">AI</span>
            </h1>
            <span className="brand-tagline">Discover • Explore • Experience</span>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeNav === item.id;
            return (
              <button
                key={item.id}
                onClick={item.action}
                className={`nav-item ${isActive ? 'active' : ''}`}
                title={item.label}
              >
                <Icon className="nav-icon" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Architectural Etching & Quote */}
      <div className="sidebar-bottom">
        <div className="sidebar-art-container">
          <img 
            src="/static/assets/sidebar_art.png" 
            alt="Temple Art Illustration" 
            className="sidebar-art-img"
            onError={(e) => {
              e.target.style.display = 'none';
            }}
          />
        </div>
      </div>
    </aside>
  );
}
