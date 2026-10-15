/**
 * PilgrimAI Frontend API Client
 * Connects directly to real backend endpoints.
 */

const BASE_URL = ''; // Relative path for proxy / static serving

function getAuthHeader() {
  const token = localStorage.getItem('pilgrim_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function askChat(question, sessionId = null) {
  const payload = { question };
  if (sessionId) {
    payload.session_id = sessionId;
  }
  const response = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Chat request failed with status ${response.status}`);
  }
  return await response.json();
}

export async function getTemples() {
  const response = await fetch(`${BASE_URL}/api/maps/temples`);
  if (!response.ok) {
    throw new Error(`Failed to load temples (${response.status})`);
  }
  return await response.json();
}

export async function getMapsConfig() {
  const response = await fetch(`${BASE_URL}/api/maps/config`);
  if (!response.ok) {
    throw new Error(`Failed to load maps config (${response.status})`);
  }
  return await response.json();
}

export async function getChatHistory() {
  const response = await fetch(`${BASE_URL}/api/chat/history`, {
    headers: { ...getAuthHeader() },
  });
  if (!response.ok) {
    return [];
  }
  return await response.json();
}

export async function getChatSession(sessionId) {
  const response = await fetch(`${BASE_URL}/api/chat/history/${encodeURIComponent(sessionId)}`, {
    headers: { ...getAuthHeader() },
  });
  if (!response.ok) {
    throw new Error(`Failed to load session history (${response.status})`);
  }
  return await response.json();
}

export async function loginUser(email, password) {
  const response = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Login failed. Please check your credentials.');
  }
  return await response.json();
}

export async function registerUser(email, password, name) {
  const response = await fetch(`${BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Registration failed.');
  }
  return await response.json();
}

export async function getCurrentUser(token) {
  const t = token || localStorage.getItem('pilgrim_token');
  if (!t) return null;
  const response = await fetch(`${BASE_URL}/api/auth/me`, {
    headers: {
      Authorization: `Bearer ${t}`,
    },
  });
  if (!response.ok) {
    return null;
  }
  return await response.json();
}

export async function planItinerary(payload) {
  const response = await fetch(`${BASE_URL}/api/itinerary/plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Itinerary planning failed (${response.status})`);
  }
  return await response.json();
}

export async function saveItinerary(payload) {
  const response = await fetch(`${BASE_URL}/api/itinerary/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to save itinerary (${response.status})`);
  }
  return await response.json();
}

export async function getSavedItineraries() {
  const response = await fetch(`${BASE_URL}/api/itinerary/saved`, {
    headers: { ...getAuthHeader() },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to load saved itineraries (${response.status})`);
  }
  return await response.json();
}

export async function deleteSavedItinerary(itineraryId) {
  const response = await fetch(`${BASE_URL}/api/itinerary/saved/${encodeURIComponent(itineraryId)}`, {
    method: 'DELETE',
    headers: { ...getAuthHeader() },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete itinerary (${response.status})`);
  }
  return await response.json();
}
