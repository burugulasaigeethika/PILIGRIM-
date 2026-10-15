import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import HeroBanner from './components/HeroBanner';
import FeatureCards from './components/FeatureCards';
import PopularTemples from './components/PopularTemples';
import AskPilgrimAI from './components/AskPilgrimAI';
import StatisticsStrip from './components/StatisticsStrip';
import TempleDetailsModal from './components/TempleDetailsModal';
import ExploreTemplesModal from './components/ExploreTemplesModal';
import TripPlannerModal from './components/TripPlannerModal';
import SavedItinerariesModal from './components/SavedItinerariesModal';
import ChatHistoryModal from './components/ChatHistoryModal';
import AuthModal from './components/AuthModal';
import AboutModal from './components/AboutModal';
import TravelAssistantModal from './components/TravelAssistantModal';
import { ChatProvider, useChat } from './context/ChatContext';
import { getCurrentUser } from './services/api';
import './styles/dashboard.css';

function MainDashboard() {
  const [activeNav, setActiveNav] = useState('dashboard');
  const [user, setUser] = useState(null);

  const { 
    isFullChatOpen, 
    setIsFullChatOpen, 
    sendMessage 
  } = useChat();
  
  // Modals state
  const [selectedTemple, setSelectedTemple] = useState(null);
  const [showExploreModal, setShowExploreModal] = useState(false);
  const [showTripPlanner, setShowTripPlanner] = useState(false);
  const [showSavedItineraries, setShowSavedItineraries] = useState(false);
  const [showChatHistory, setShowChatHistory] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showAboutModal, setShowAboutModal] = useState(false);

  // Auto-login if token exists
  useEffect(() => {
    const token = localStorage.getItem('pilgrim_token');
    if (token) {
      getCurrentUser(token)
        .then((userData) => {
          if (userData) setUser(userData);
        })
        .catch(() => {
          localStorage.removeItem('pilgrim_token');
        });
    }
  }, []);

  const handleSearch = (query) => {
    sendMessage(query);
    setIsFullChatOpen(true);
  };

  const handleAskAboutTemple = (question) => {
    sendMessage(question);
    setIsFullChatOpen(true);
  };

  const handleContinueInChatFromPlanner = (queryText) => {
    sendMessage(queryText);
    setIsFullChatOpen(true);
  };

  return (
    <div className="app-layout">
      {/* Left Sidebar */}
      <Sidebar 
        activeNav={activeNav}
        setActiveNav={setActiveNav}
        onOpenAssistant={() => setIsFullChatOpen(true)}
        onOpenTripPlanner={() => setShowTripPlanner(true)}
        onOpenSavedItineraries={() => setShowSavedItineraries(true)}
        onOpenChatHistory={() => setShowChatHistory(true)}
        onOpenAbout={() => setShowAboutModal(true)}
        onOpenExplore={() => setShowExploreModal(true)}
      />

      {/* Main Content Area */}
      <div className="main-wrapper">
        <Topbar 
          user={user}
          onOpenAuth={() => setShowAuthModal(true)}
          onSearch={handleSearch}
        />

        <main className="dashboard-content">
          {/* Hero Banner */}
          <HeroBanner 
            onExploreTemples={() => setShowExploreModal(true)}
            onPlanTrip={() => setShowTripPlanner(true)}
          />

          {/* 4 Feature Cards */}
          <FeatureCards 
            onExploreTemples={() => setShowExploreModal(true)}
            onOpenAssistant={() => setIsFullChatOpen(true)}
            onOpenTripPlanner={() => setShowTripPlanner(true)}
            onOpenChatHistory={() => setShowChatHistory(true)}
          />

          {/* Middle Two-Column Grid: Popular Temples (Left) & Ask PilgrimAI (Right) */}
          <div className="middle-grid">
            <PopularTemples 
              onSelectTemple={(temple) => setSelectedTemple(temple)}
              onViewAll={() => setShowExploreModal(true)}
            />

            <AskPilgrimAI />
          </div>

          {/* Bottom Statistics Strip */}
          <StatisticsStrip />
        </main>
      </div>

      {/* Full-Page Expanded Chat Modal */}
      <TravelAssistantModal 
        isOpen={isFullChatOpen}
        onClose={() => setIsFullChatOpen(false)}
      />

      {/* Modals */}
      <TempleDetailsModal 
        temple={selectedTemple}
        onClose={() => setSelectedTemple(null)}
        onAskAboutTemple={handleAskAboutTemple}
      />

      <ExploreTemplesModal 
        isOpen={showExploreModal}
        onClose={() => setShowExploreModal(false)}
        onSelectTemple={(temple) => setSelectedTemple(temple)}
      />

      <TripPlannerModal 
        isOpen={showTripPlanner}
        onClose={() => setShowTripPlanner(false)}
        onContinueInChat={handleContinueInChatFromPlanner}
        onRequireAuth={() => setShowAuthModal(true)}
      />

      <SavedItinerariesModal 
        isOpen={showSavedItineraries}
        onClose={() => setShowSavedItineraries(false)}
        onContinueInChat={handleContinueInChatFromPlanner}
        onOpenAuth={() => setShowAuthModal(true)}
      />

      <ChatHistoryModal 
        isOpen={showChatHistory}
        onClose={() => setShowChatHistory(false)}
        user={user}
        onOpenAuth={() => setShowAuthModal(true)}
      />

      <AuthModal 
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        user={user}
        onAuthSuccess={(u) => setUser(u)}
        onLogout={() => setUser(null)}
      />

      <AboutModal 
        isOpen={showAboutModal}
        onClose={() => setShowAboutModal(false)}
      />
    </div>
  );
}

export default function App() {
  return (
    <ChatProvider>
      <MainDashboard />
    </ChatProvider>
  );
}
