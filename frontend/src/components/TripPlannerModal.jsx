import React, { useState } from 'react';
import { 
  X, 
  Calendar, 
  MapPin, 
  Users, 
  DollarSign, 
  Car, 
  Sparkles, 
  ArrowLeft, 
  Bookmark, 
  MessageSquare, 
  Loader2,
  CheckCircle,
  AlertCircle,
  ExternalLink,
  Navigation,
  Plus,
  Landmark,
  Compass,
  Check
} from 'lucide-react';
import { 
  planItinerary, 
  saveItinerary, 
  getNearbyPlaces, 
  generateGoogleMapsSearchUrl, 
  generateGoogleMapsDirectionsUrl 
} from '../services/api';
import StructuredCards from './StructuredCards';

export default function TripPlannerModal({ 
  isOpen, 
  onClose, 
  onContinueInChat,
  onRequireAuth
}) {
  const [activeTab, setActiveTab] = useState('form'); // 'form' | 'result'
  const [origin, setOrigin] = useState('Hyderabad');
  const [roundTrip, setRoundTrip] = useState(false);
  const [selectedDestinations, setSelectedDestinations] = useState(['Yadadri']);
  const [duration, setDuration] = useState(1);
  const [startDate, setStartDate] = useState('');
  const [pax, setPax] = useState(1);
  const [budgetLimit, setBudgetLimit] = useState('');
  const [accommodation, setAccommodation] = useState('');
  const [transport, setTransport] = useState('');
  const [food, setFood] = useState('');

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [planResult, setPlanResult] = useState(null);

  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // { type: 'success' | 'error', message: string }

  // Nearby attractions & interactive recalculation states
  const [nearbyPlaces, setNearbyPlaces] = useState({}); // { [dest]: PlaceResultItem[] }
  const [loadingPlaces, setLoadingPlaces] = useState(false);
  const [selectedActivities, setSelectedActivities] = useState([]); // [{ name, destination, day }]
  const [selectedDaysByPlace, setSelectedDaysByPlace] = useState({}); // { [placeName]: dayNumber }
  const [recalculating, setRecalculating] = useState(false);

  // 20 Certified Temples matching backend
  const certifiedTemples = [
    { id: 'Yadadri', name: 'Yadadri' },
    { id: 'Basara', name: 'Basara' },
    { id: 'Srisailam', name: 'Srisailam' },
    { id: 'Bhadrachalam', name: 'Bhadrachalam' },
    { id: 'Vemulavada', name: 'Vemulavada' },
    { id: 'Ramappa', name: 'Ramappa' },
    { id: 'Thousand Pillar', name: 'Thousand Pillar' },
    { id: 'Birla Mandir', name: 'Birla Mandir' },
    { id: 'Karmanghat', name: 'Karmanghat' },
    { id: 'Ujjaini', name: 'Ujjaini Mahakali' },
    { id: 'Edupayal', name: 'Edupayala' },
    { id: 'Dharmapuri', name: 'Dharmapuri' },
    { id: 'Balkampet', name: 'Balkampet' },
    { id: 'Ttd', name: 'Tirumala (TTD)' },
    { id: 'Jogulamba', name: 'Jogulamba' },
    { id: 'Ahobilam', name: 'Ahobilam' },
    { id: 'Chilkur', name: 'Chilkur Balaji' },
    { id: 'Kaleshwaram', name: 'Kaleshwaram' },
    { id: 'Medaram', name: 'Medaram' },
    { id: 'Veera Satyanarayana', name: 'Annavaram Satyanarayana' },
  ];

  if (!isOpen) return null;

  const toggleDestination = (templeId) => {
    setErrorMsg(null);
    let updated;
    if (selectedDestinations.includes(templeId)) {
      updated = selectedDestinations.filter(d => d !== templeId);
    } else {
      updated = [...selectedDestinations, templeId];
    }
    setSelectedDestinations(updated);
    if (updated.length > 0 && duration <= 1) {
      setDuration(Math.max(1, updated.length));
    }
  };

  const getValidDaysForDestination = (dest, destinations, durationDays) => {
    if (!destinations || destinations.length === 0) return [1];
    const cleanDests = destinations.map(d => String(d).toLowerCase().trim());
    const targetClean = String(dest).toLowerCase().trim();
    const idx = cleanDests.findIndex(d => d === targetClean || targetClean.includes(d) || d.includes(targetClean));
    const n = destinations.length;
    const totalDays = Math.max(1, parseInt(durationDays, 10) || 1);
    if (idx === -1) return [1];
    if (totalDays < n) {
      const targetDay = Math.min(Math.floor(idx * totalDays / n), totalDays - 1) + 1;
      return [targetDay];
    }
    const baseDays = Math.floor(totalDays / n);
    const extra = totalDays % n;
    let startDay = 1;
    for (let i = 0; i < idx; i++) {
      startDay += baseDays + (i < extra ? 1 : 0);
    }
    const daysForDest = baseDays + (idx < extra ? 1 : 0);
    const days = [];
    for (let d = 0; d < daysForDest; d++) {
      days.push(startDay + d);
    }
    return days.length > 0 ? days : [1];
  };

  const loadNearbyAttractions = async (dests) => {
    if (!dests || dests.length === 0) return;
    setLoadingPlaces(true);
    const results = {};
    for (const dest of dests) {
      try {
        const data = await getNearbyPlaces(dest, 'all');
        results[dest] = data.results || data.places || [];
      } catch (err) {
        console.warn(`[Places Discovery] Failed to load places for ${dest}:`, err);
        results[dest] = [];
      }
    }
    setNearbyPlaces(results);
    setLoadingPlaces(false);
  };

  const recalculateWithActivities = async (newActivities) => {
    if (!planResult) return;
    setRecalculating(true);
    setErrorMsg(null);

    const payload = {
      origin: origin.trim() || null,
      destinations: selectedDestinations,
      duration_days: parseInt(duration, 10) || selectedDestinations.length,
      start_date: startDate || null,
      pax: parseInt(pax, 10) || 1,
      budget_limit: budgetLimit ? parseFloat(budgetLimit) : null,
      accommodation_preference: accommodation || null,
      transport_preference: transport || null,
      food_preference: food || null,
      round_trip: roundTrip,
      selected_activities: newActivities,
    };

    try {
      const res = await planItinerary(payload);
      setPlanResult(res);
    } catch (err) {
      setErrorMsg(`Recalculation error: ${err.message}`);
    } finally {
      setRecalculating(false);
    }
  };

  const handleAddActivity = (dest, place, targetDay) => {
    const isAdded = selectedActivities.some(
      a => a.name.toLowerCase() === place.name.toLowerCase()
    );
    if (isAdded) return;

    const newAct = {
      name: place.name,
      destination: dest,
      day: parseInt(targetDay, 10) || 1,
    };
    const nextList = [...selectedActivities, newAct];
    setSelectedActivities(nextList);
    recalculateWithActivities(nextList);
  };

  const handleRemoveActivity = (indexToRemove) => {
    const nextList = selectedActivities.filter((_, idx) => idx !== indexToRemove);
    setSelectedActivities(nextList);
    recalculateWithActivities(nextList);
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setSaveStatus(null);

    if (selectedDestinations.length === 0) {
      setErrorMsg("Please select at least one pilgrimage destination from the registered list.");
      return;
    }

    setLoading(true);

    const payload = {
      origin: origin.trim() || null,
      destinations: selectedDestinations,
      duration_days: parseInt(duration, 10) || selectedDestinations.length,
      start_date: startDate || null,
      pax: parseInt(pax, 10) || 1,
      budget_limit: budgetLimit ? parseFloat(budgetLimit) : null,
      accommodation_preference: accommodation || null,
      transport_preference: transport || null,
      food_preference: food || null,
      round_trip: roundTrip,
    };

    try {
      const res = await planItinerary(payload);
      setPlanResult(res);
      setSelectedActivities([]);
      setActiveTab('result');
      loadNearbyAttractions(selectedDestinations);
    } catch (err) {
      setErrorMsg(err.message || "Failed to generate itinerary. Ensure backend server is healthy.");
    } finally {
      setLoading(false);
    }
  };

  const handleSavePlan = async () => {
    if (!planResult) return;
    const token = localStorage.getItem('pilgrim_token');
    if (!token) {
      setSaveStatus({
        type: 'error',
        message: 'Please sign in to your pilgrim account to save itineraries.',
      });
      if (onRequireAuth) onRequireAuth();
      return;
    }

    setSaving(true);
    setSaveStatus(null);

    const p = planResult.parameters || {};
    const meta = planResult.metadata || {};

    const savePayload = {
      title: `Pilgrimage to ${selectedDestinations.join(' & ')} (${p.duration_days || duration} Days)`,
      origin: p.origin || origin || null,
      destinations: selectedDestinations,
      duration_days: p.duration_days || duration,
      pax: p.pax || pax,
      budget_limit: p.budget_limit || (budgetLimit ? parseFloat(budgetLimit) : null),
      preferences: p.preferences || {},
      itinerary_text: planResult.answer || planResult.itinerary || '',
      route_legs: meta.route_legs || [],
      budget_breakdown: meta.calculated_total || {},
    };

    try {
      await saveItinerary(savePayload);
      setSaveStatus({
        type: 'success',
        message: '✓ Itinerary saved successfully to your profile!',
      });
    } catch (err) {
      setSaveStatus({
        type: 'error',
        message: `Save failed: ${err.message}`,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleContinueInChat = () => {
    if (!planResult) return;
    onClose();
    if (onContinueInChat) {
      const queryUsed = planResult.query_used || `Plan a ${duration} day pilgrimage to ${selectedDestinations.join(' and ')}`;
      onContinueInChat(queryUsed, planResult);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="modal-content" 
        style={{ maxWidth: 740, maxHeight: '90vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#E6F3EA', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#2E7D4E' }}>
              <Calendar size={18} />
            </div>
            <div>
              <h3 className="modal-title">Plan a Pilgrimage Itinerary</h3>
              <p style={{ fontSize: '0.72rem', color: '#6A7870', margin: 0 }}>
                Timing-aware schedules, multi-destination routing & verified budget estimation
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Tab Switcher if result exists */}
        {planResult && (
          <div className="planner-tabs-bar">
            <button 
              type="button" 
              className={`planner-tab-btn ${activeTab === 'form' ? 'active' : ''}`}
              onClick={() => setActiveTab('form')}
            >
              1. Trip Parameters
            </button>
            <button 
              type="button" 
              className={`planner-tab-btn ${activeTab === 'result' ? 'active' : ''}`}
              onClick={() => setActiveTab('result')}
            >
              2. Generated Itinerary & Budget
            </button>
          </div>
        )}

        {/* Body View */}
        <div className="modal-body">
          {activeTab === 'form' ? (
            <form onSubmit={handleGenerate} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Origin and Round Trip */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 14, alignItems: 'center' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#123C32', marginBottom: 4 }}>
                    Starting City / Origin <span style={{ fontWeight: 400, color: '#8A9890' }}>(Optional)</span>
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Hyderabad, Warangal, Secunderabad"
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', border: '1px solid #E2DDD1', borderRadius: 8, fontSize: '0.86rem' }}
                  />
                  <span style={{ fontSize: '0.7rem', color: '#8A9890', marginTop: 2, display: 'block' }}>
                    Leave blank for temple-to-temple schedule
                  </span>
                </div>

                <div style={{ paddingTop: 10 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.82rem', color: '#123C32', fontWeight: 600 }}>
                    <input
                      type="checkbox"
                      checked={roundTrip}
                      onChange={(e) => setRoundTrip(e.target.checked)}
                      style={{ width: 16, height: 16, accentColor: '#123C32' }}
                    />
                    <span>Include return journey back to origin</span>
                  </label>
                </div>
              </div>

              {/* Destination Chips Multi-Selector */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#123C32', marginBottom: 6 }}>
                  Pilgrimage Destinations * <span style={{ fontWeight: 500, color: '#D96B24' }}>(Select 1 or more registered temples)</span>
                </label>
                <div className="destinations-chips-selector">
                  {certifiedTemples.map((t) => {
                    const isSelected = selectedDestinations.includes(t.id);
                    return (
                      <button
                        type="button"
                        key={t.id}
                        onClick={() => toggleDestination(t.id)}
                        className={`dest-chip-btn ${isSelected ? 'selected' : ''}`}
                      >
                        {isSelected ? '✓ ' : ''}{t.name}
                      </button>
                    );
                  })}
                </div>

                {selectedDestinations.length > 0 && (
                  <div className="route-sequence-banner">
                    <MapPin size={14} />
                    <span>Route Sequence: {selectedDestinations.join(' ➔ ')}</span>
                  </div>
                )}
              </div>

              {/* Grid: Duration, Start Date, Pax, Budget */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: '#123C32', marginBottom: 4 }}>
                    Duration (Days)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="14"
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
                    style={{ width: '100%', padding: '6px 10px', border: '1px solid #E2DDD1', borderRadius: 8, fontSize: '0.84rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: '#123C32', marginBottom: 4 }}>
                    Start Date <span style={{ fontWeight: 400, color: '#8A9890' }}>(Opt)</span>
                  </label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    style={{ width: '100%', padding: '6px 10px', border: '1px solid #E2DDD1', borderRadius: 8, fontSize: '0.82rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: '#123C32', marginBottom: 4 }}>
                    Pilgrims (Group)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={pax}
                    onChange={(e) => setPax(e.target.value)}
                    style={{ width: '100%', padding: '6px 10px', border: '1px solid #E2DDD1', borderRadius: 8, fontSize: '0.84rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: '#123C32', marginBottom: 4 }}>
                    Budget Limit (₹)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="500"
                    placeholder="e.g. 5000"
                    value={budgetLimit}
                    onChange={(e) => setBudgetLimit(e.target.value)}
                    style={{ width: '100%', padding: '6px 10px', border: '1px solid #E2DDD1', borderRadius: 8, fontSize: '0.84rem' }}
                  />
                </div>
              </div>

              {/* Preferences: Accommodation, Transport, Food */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: '#123C32', marginBottom: 4 }}>
                    Accommodation Tier
                  </label>
                  <select
                    value={accommodation}
                    onChange={(e) => setAccommodation(e.target.value)}
                    style={{ width: '100%', padding: '7px 10px', border: '1px solid #E2DDD1', borderRadius: 8, fontSize: '0.82rem', background: '#FFFFFF' }}
                  >
                    <option value="">No preference (Baseline)</option>
                    <option value="budget">Budget (Lodge / Satram)</option>
                    <option value="standard">Standard (Guest House / AC)</option>
                    <option value="premium">Premium (Resort / Haritha)</option>
                    <option value="none">No Accommodation (Day Trip)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: '#123C32', marginBottom: 4 }}>
                    Transport Mode
                  </label>
                  <select
                    value={transport}
                    onChange={(e) => setTransport(e.target.value)}
                    style={{ width: '100%', padding: '7px 10px', border: '1px solid #E2DDD1', borderRadius: 8, fontSize: '0.82rem', background: '#FFFFFF' }}
                  >
                    <option value="">No preference (Compare)</option>
                    <option value="car">Personal Car / Taxi</option>
                    <option value="bus">TSRTC / Public Bus</option>
                    <option value="train">Indian Railways</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: '#123C32', marginBottom: 4 }}>
                    Food & Dining
                  </label>
                  <select
                    value={food}
                    onChange={(e) => setFood(e.target.value)}
                    style={{ width: '100%', padding: '7px 10px', border: '1px solid #E2DDD1', borderRadius: 8, fontSize: '0.82rem', background: '#FFFFFF' }}
                  >
                    <option value="">No preference (Baseline)</option>
                    <option value="prasadam">Temple Prasadam / Annadanam</option>
                    <option value="dining">Local Dining / Restaurants</option>
                  </select>
                </div>
              </div>

              {errorMsg && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#FDF2F2', border: '1px solid #F6C4C4', color: '#D9383A', padding: '8px 12px', borderRadius: 8, fontSize: '0.8rem' }}>
                  <AlertCircle size={16} />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Action */}
              <div style={{ marginTop: 8 }}>
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-hero-primary"
                  style={{ width: '100%', justifyContent: 'center', padding: '10px 20px', fontSize: '0.9rem' }}
                >
                  {loading ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      <span>Generating Verified Itinerary & Budget...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      <span>Generate Verified Itinerary & Budget</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : (
            /* Results View */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Action Bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 10, borderBottom: '1px solid #E8E2D5' }}>
                <button
                  type="button"
                  onClick={() => setActiveTab('form')}
                  className="btn-chat-header"
                >
                  <ArrowLeft size={14} />
                  <span>Edit Parameters</span>
                </button>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    onClick={handleSavePlan}
                    disabled={saving}
                    className="btn-chat-header"
                    style={{ background: '#FAF0DE', borderColor: '#E5CBA2', color: '#8C5611' }}
                    title="Save this itinerary to your profile"
                  >
                    {saving ? <Loader2 size={13} className="animate-spin" /> : <Bookmark size={13} />}
                    <span>{saving ? 'Saving...' : 'Save Itinerary'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleContinueInChat}
                    className="btn-hero-primary"
                    style={{ padding: '5px 14px', fontSize: '0.78rem' }}
                    title="Discuss this itinerary in the full interactive chat"
                  >
                    <MessageSquare size={13} />
                    <span>Continue in Chat</span>
                  </button>
                </div>
              </div>

              {saveStatus && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: saveStatus.type === 'success' ? '#EEF7EF' : '#FDF2F2', border: `1px solid ${saveStatus.type === 'success' ? '#D5EBD7' : '#F6C4C4'}`, color: saveStatus.type === 'success' ? '#2E7D4E' : '#D9383A', padding: '8px 12px', borderRadius: 8, fontSize: '0.8rem' }}>
                  {saveStatus.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                  <span>{saveStatus.message}</span>
                </div>
              )}

              {/* Recalculating status indicator */}
              {recalculating && (
                <div className="recalculating-overlay">
                  <Loader2 size={16} className="animate-spin" />
                  <span>Updating itinerary schedule and budget with custom activities...</span>
                </div>
              )}

              {/* Added Custom Activities Bar */}
              {selectedActivities.length > 0 && (
                <div className="added-activities-bar">
                  <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#D96B24' }}>
                    Custom Activities Added ({selectedActivities.length}):
                  </span>
                  {selectedActivities.map((act, actIdx) => (
                    <div key={actIdx} className="added-act-tag">
                      <span>📅 Day {act.day}: <strong>{act.name}</strong> ({act.destination})</span>
                      <button
                        type="button"
                        className="btn-remove-act"
                        onClick={() => handleRemoveActivity(actIdx)}
                        title="Remove activity from schedule"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Render Structured Cards if available in metadata */}
              {planResult.metadata && <StructuredCards metadata={planResult.metadata} />}

              {/* Nearby Attractions Discovery Section */}
              <div className="planner-places-section">
                <div className="planner-places-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Compass size={18} color="#D96B24" />
                    <div>
                      <h4 style={{ margin: 0, fontSize: '0.92rem', color: '#123C32', fontWeight: 700 }}>
                        Nearby Attractions & Custom Activities
                      </h4>
                      <p style={{ margin: 0, fontSize: '0.72rem', color: '#6A7870' }}>
                        Add verified historical forts, viewpoints, and cultural spots into your itinerary
                      </p>
                    </div>
                  </div>
                  {loadingPlaces && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.74rem', color: '#6A7870' }}>
                      <Loader2 size={13} className="animate-spin" />
                      <span>Loading places...</span>
                    </div>
                  )}
                </div>

                {selectedDestinations.map((dest) => {
                  const places = nearbyPlaces[dest] || [];
                  const validDays = getValidDaysForDestination(dest, selectedDestinations, duration);

                  return (
                    <div key={dest} style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#123C32', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Landmark size={14} color="#2E7D4E" />
                        <span>Attractions near {dest}</span>
                        <span style={{ fontSize: '0.7rem', fontWeight: 500, color: '#8A9890' }}>
                          ({places.length} available)
                        </span>
                      </div>

                      {places.length === 0 ? (
                        <div style={{ fontSize: '0.75rem', color: '#8A9890', padding: '6px 0' }}>
                          {loadingPlaces ? 'Fetching attractions...' : `No additional attractions found near ${dest}.`}
                        </div>
                      ) : (
                        <div className="planner-attractions-grid">
                          {places.slice(0, 8).map((p, pIdx) => {
                            const addedItem = selectedActivities.find(
                              (a) => a.name.toLowerCase() === p.name.toLowerCase()
                            );
                            const currentTargetDay = selectedDaysByPlace[p.name] || validDays[0] || 1;
                            const searchUrl = p.map_url || generateGoogleMapsSearchUrl(p.name, dest);
                            const dirUrl = p.directions_url || generateGoogleMapsDirectionsUrl(dest, p.name);

                            return (
                              <div key={pIdx} className="planner-attraction-card">
                                <div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6, marginBottom: 4 }}>
                                    <h5 className="attraction-card-title">{p.name}</h5>
                                    {p.distance && (
                                      <span style={{ fontSize: '0.7rem', color: '#D96B24', fontWeight: 700, whiteSpace: 'nowrap' }}>
                                        {p.distance}
                                      </span>
                                    )}
                                  </div>

                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                                    <span className="attraction-badge-pill attraction-badge-category">
                                      {p.category || 'Sightseeing'}
                                    </span>
                                    <span className={`attraction-badge-pill ${p.source && p.source.includes('Google') ? 'attraction-badge-source-google' : 'attraction-badge-source-verified'}`}>
                                      {p.source && p.source.includes('Google') ? 'Google Places' : 'Temple Knowledge Base'}
                                    </span>
                                  </div>

                                  {p.description && (
                                    <p style={{ fontSize: '0.74rem', color: '#55655E', margin: '0 0 6px 0', lineHeight: 1.4 }}>
                                      {p.description}
                                    </p>
                                  )}
                                </div>

                                <div className="attraction-actions-row">
                                  <div className="attraction-links-group">
                                    <a
                                      href={searchUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="attraction-link-btn"
                                      title="View on Google Maps"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <ExternalLink size={11} />
                                      <span>Map</span>
                                    </a>
                                    <a
                                      href={dirUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="attraction-link-btn"
                                      title="Get Directions on Google Maps"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <Navigation size={11} />
                                      <span>Route</span>
                                    </a>
                                  </div>

                                  <div className="attraction-add-group">
                                    {addedItem ? (
                                      <span className="btn-add-activity-pill added">
                                        <Check size={11} />
                                        <span>Added (Day {addedItem.day})</span>
                                      </span>
                                    ) : (
                                      <>
                                        <select
                                          className="attraction-day-select"
                                          value={currentTargetDay}
                                          onChange={(e) =>
                                            setSelectedDaysByPlace({
                                              ...selectedDaysByPlace,
                                              [p.name]: parseInt(e.target.value, 10),
                                            })
                                          }
                                        >
                                          {validDays.map((d) => (
                                            <option key={d} value={d}>
                                              Day {d}
                                            </option>
                                          ))}
                                        </select>
                                        <button
                                          type="button"
                                          className="btn-add-activity-pill"
                                          onClick={() => handleAddActivity(dest, p, currentTargetDay)}
                                          disabled={recalculating}
                                          title={`Add ${p.name} to Day ${currentTargetDay}`}
                                        >
                                          <Plus size={11} />
                                          <span>Add to Day</span>
                                        </button>
                                      </>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Full Formatted Itinerary Text */}
              <div style={{ background: '#FAF8F3', border: '1px solid #E8E2D5', borderRadius: 12, padding: 18, maxHeight: 420, overflowY: 'auto' }}>
                <h4 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.15rem', color: '#123C32', marginBottom: 10 }}>
                  {planResult.parameters ? `Pilgrimage to ${planResult.parameters.destinations.join(' & ')}` : 'Generated Pilgrimage Itinerary'}
                </h4>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.86rem', color: '#1A2420', lineHeight: 1.6 }}>
                  {planResult.answer || planResult.itinerary}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
