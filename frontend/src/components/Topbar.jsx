import React, { useState } from 'react';
import { Search, Bell, ChevronDown } from 'lucide-react';

export default function Topbar({ user, onOpenAuth, onSearch }) {
  const [query, setQuery] = useState('');

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && onSearch) {
      onSearch(query.trim());
    }
  };

  const initial = user?.name ? user.name.charAt(0).toUpperCase() : 'S';
  const displayName = user?.name || 'User';

  return (
    <header className="topbar">
      <form onSubmit={handleSearchSubmit} className="search-box-container">
        <Search className="search-icon" />
        <input
          type="text"
          className="search-input"
          placeholder="Search temples, destinations, or ask anything..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" className="search-btn">
          Search
        </button>
      </form>

      <div className="topbar-actions">
        <button 
          className="icon-badge-btn" 
          title="Notifications" 
          onClick={() => alert("All offline pilgrimage services and local RAG models are currently healthy and operational.")}
        >
          <Bell size={18} />
        </button>

        <button 
          className="user-profile-btn" 
          onClick={onOpenAuth}
          title={user ? `Signed in as ${user.email}` : "Sign In / Register"}
        >
          <div className="user-avatar-circle">
            {initial}
          </div>
          <div className="user-greeting">
            <span className="user-greeting-label">Hello,</span>
            <span className="user-greeting-name">{displayName}</span>
          </div>
          <ChevronDown size={14} color="#6C5A48" />
        </button>
      </div>
    </header>
  );
}
