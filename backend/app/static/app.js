/**
 * PilgrimAI — Intelligent Pilgrimage Assistant
 * Frontend Controller: Multi-Turn Session Memory, Active Agent Display,
 * Structured Cards, Google Maps JavaScript, Places & Routes Integration,
 * Native Browser Voice UI (STT/TTS), and Multilingual Support.
 */

document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // DOM Elements
    // -------------------------------------------------------------
    const chatForm = document.getElementById("chatForm");
    const userQuery = document.getElementById("userQuery");
    const messageArea = document.getElementById("messageArea");
    const submitBtn = document.getElementById("submitBtn");
    const newChatBtn = document.getElementById("newChatBtn");
    const micBtn = document.getElementById("micBtn");
    const toggleMapBtn = document.getElementById("toggleMapBtn");
    const tabMapBtn = document.getElementById("tabMapBtn");
    const tabPlacesBtn = document.getElementById("tabPlacesBtn");
    const mapPanel = document.getElementById("mapPanel");
    const mapFallback = document.getElementById("mapFallback");
    const placesList = document.getElementById("placesList");
    const placesTargetTitle = document.getElementById("placesTargetTitle");
    const templeList = document.getElementById("templeList");
    const langChips = document.querySelectorAll(".lang-chip");

    // -------------------------------------------------------------
    // State Management
    // -------------------------------------------------------------
    let currentSessionId = getOrCreateSessionId();
    let currentLang = "en";
    let currentSelectedTemple = "Sri Lakshmi Narasimha Swamy Temple, Yadadri";
    let currentLat = 17.587714;
    let currentLng = 78.948325;
    let placesRequestStarted = false;
    let placesLastStatus = "NOT_STARTED";
    let placesLastResultCount = 0;
    let placesLastError = null;
    let googleMap = null;
    let mapMarkers = [];
    let directionsRenderer = null;
    let directionsService = null;
    let activeRoutePolyline = null;
    let activeRouteMarkers = [];
    const VERIFIED_TEMPLE_REGISTRY = [
        { canonical_name: "Ahobilam", display_name: "Sri Ahobila Narasimha Swamy Temple", latitude: 15.127814, longitude: 78.718048, district: "Nandyal", state: "Andhra Pradesh" },
        { canonical_name: "Badrachalam", display_name: "Sri Sita Ramachandraswamy Temple, Bhadrachalam", latitude: 17.669822, longitude: 80.893641, district: "Bhadradri Kothagudem", state: "Telangana" },
        { canonical_name: "Balkampet", display_name: "Balkampet Yellamma Temple, Hyderabad", latitude: 17.447528, longitude: 78.451639, district: "Hyderabad", state: "Telangana" },
        { canonical_name: "Basara", display_name: "Sri Gnana Saraswathi Devasthanam, Basara", latitude: 18.870451, longitude: 77.954153, district: "Nirmal", state: "Telangana" },
        { canonical_name: "Birla Mandir", display_name: "Birla Mandir, Hyderabad", latitude: 17.40429, longitude: 78.469146, district: "Hyderabad", state: "Telangana" },
        { canonical_name: "Chilkur", display_name: "Chilkur Balaji Temple", latitude: 17.378281, longitude: 78.297491, district: "Rangareddy", state: "Telangana" },
        { canonical_name: "Dharmapuri", display_name: "Sri Lakshmi Narasimha Swamy Temple, Dharmapuri", latitude: 18.95152, longitude: 79.09171, district: "Jagtial", state: "Telangana" },
        { canonical_name: "Edupayal", display_name: "Sri Edupayala Vana Durga Bhavani Devalayam", latitude: 17.97121, longitude: 78.17552, district: "Medak", state: "Telangana" },
        { canonical_name: "Jogulamba(New)", display_name: "Jogulamba Devi Temple, Alampur", latitude: 15.876984, longitude: 78.134864, district: "Jogulamba Gadwal", state: "Telangana" },
        { canonical_name: "Kaleshvaram", display_name: "Sri Kaleshwara Mukteshwara Swamy Temple, Kaleshwaram", latitude: 18.811821, longitude: 79.904026, district: "Jayashankar Bhupalpally", state: "Telangana" },
        { canonical_name: "Karmanghat", display_name: "Karmanghat Hanuman Temple, Hyderabad", latitude: 17.341166, longitude: 78.522387, district: "Hyderabad", state: "Telangana" },
        { canonical_name: "Medaram", display_name: "Sammakka Saralamma Gaddelu, Medaram", latitude: 18.2259, longitude: 79.9463, district: "Mulugu", state: "Telangana" },
        { canonical_name: "Ramappa", display_name: "Ramappa Temple, Palampet", latitude: 18.256242, longitude: 79.940562, district: "Mulugu", state: "Telangana" },
        { canonical_name: "Srisaila", display_name: "Sri Bhramaramba Mallikarjuna Swamy Temple, Srisailam", latitude: 16.0742, longitude: 78.868199, district: "Nandyal", state: "Andhra Pradesh" },
        { canonical_name: "Thousand Pillar", display_name: "Thousand Pillar Temple, Hanamkonda", latitude: 18.003737, longitude: 79.574771, district: "Hanamkonda", state: "Telangana" },
        { canonical_name: "Ttd", display_name: "Sri Venkateswara Swamy Temple, Tirumala", latitude: 13.680736, longitude: 79.350898, district: "Tirupati", state: "Andhra Pradesh" },
        { canonical_name: "Ujjaini", display_name: "Sri Ujjaini Mahakali Temple, Secunderabad", latitude: 17.441235, longitude: 78.498123, district: "Hyderabad", state: "Telangana" },
        { canonical_name: "Veera Satyanarayana", display_name: "Sri Veera Venkata Satyanarayana Swamy Temple, Annavaram", latitude: 17.280512, longitude: 82.404523, district: "Kakinada", state: "Andhra Pradesh" },
        { canonical_name: "Vemulavada", display_name: "Sri Raja Rajeshwara Swamy Temple, Vemulawada", latitude: 18.467234, longitude: 78.868728, district: "Rajanna Sircilla", state: "Telangana" },
        { canonical_name: "Yadadri", display_name: "Sri Lakshmi Narasimha Swamy Temple, Yadadri", latitude: 17.587714, longitude: 78.948325, district: "Yadadri Bhuvanagiri", state: "Telangana" }
    ];
    let templeCoordinates = [...VERIFIED_TEMPLE_REGISTRY];
    let isListening = false;
    let speechRecognition = null;

    // Initialize Icons
    if (window.lucide) {
        lucide.createIcons();
    }

    // -------------------------------------------------------------
    // Session Lifecycle Management
    // -------------------------------------------------------------
    function getOrCreateSessionId() {
        let sid = localStorage.getItem("pilgrim_session_id");
        if (!sid) {
            sid = "session_" + (crypto.randomUUID ? crypto.randomUUID() : Date.now() + "_" + Math.random().toString(36).substring(2, 9));
            localStorage.setItem("pilgrim_session_id", sid);
        }
        return sid;
    }

    function createFreshSession() {
        const freshId = "session_" + (crypto.randomUUID ? crypto.randomUUID() : Date.now() + "_" + Math.random().toString(36).substring(2, 9));
        localStorage.setItem("pilgrim_session_id", freshId);
        currentSessionId = freshId;

        // Cancel any active speech synthesis and reset controls
        if (window.speechSynthesis) {
            window.speechSynthesis.cancel();
        }
        resetActiveSpeechUi();
        clearActiveRoute();
        
        // Reset message area to initial welcome box
        messageArea.innerHTML = `
            <div class="welcome-box" id="welcomeBox">
                <h2>Namaste! New Session Started</h2>
                <p>Conversation memory reset. Ask your question below or click a suggestion:</p>
                <div class="prompt-grid">
                    <div class="prompt-card" onclick="sendPrompt('What are the timings of Yadadri temple?')">
                        🕒 <strong>Yadadri Timings</strong><br>Darshan schedule & poojas
                    </div>
                    <div class="prompt-card" onclick="sendPrompt('How far is Hyderabad from Yadadri?')">
                        🧭 <strong>Hyderabad to Yadadri</strong><br>Driving distance & duration
                    </div>
                    <div class="prompt-card" onclick="sendPrompt('What is the weather at Yadadri?')">
                        🌤️ <strong>Yadadri Weather</strong><br>Live temperature & conditions
                    </div>
                    <div class="prompt-card" onclick="sendPrompt('What will a visit to Yadadri cost?')">
                        💰 <strong>Yadadri Budget</strong><br>Verified sevas & prasadam costs
                    </div>
                </div>
            </div>
        `;
        if (directionsRenderer) {
            directionsRenderer.setDirections({ routes: [] });
        }
        if (window.lucide) lucide.createIcons();
    }

    if (newChatBtn) {
        newChatBtn.addEventListener("click", () => {
            createFreshSession();
        });
    }

    // -------------------------------------------------------------
    // Multilingual Selection Chips
    // -------------------------------------------------------------
    langChips.forEach(chip => {
        chip.addEventListener("click", () => {
            langChips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            currentLang = chip.getAttribute("data-lang");
        });
    });

    // -------------------------------------------------------------
    // Map Panel Toggle
    // -------------------------------------------------------------
    if (toggleMapBtn && mapPanel) {
        toggleMapBtn.addEventListener("click", () => {
            mapPanel.classList.toggle("collapsed");
            if (!mapPanel.classList.contains("collapsed") && googleMap) {
                google.maps.event.trigger(googleMap, "resize");
            }
        });
    }

    // -------------------------------------------------------------
    // Map / Places Tabs
    // -------------------------------------------------------------
    if (tabPlacesBtn) {
        tabPlacesBtn.addEventListener("click", () => {
            if (mapPanel && mapPanel.classList.contains("collapsed")) {
                mapPanel.classList.remove("collapsed");
            }
            if (tabMapBtn) tabMapBtn.classList.remove("active");
            tabPlacesBtn.classList.add("active");

            // Show loading state on button
            const originalText = tabPlacesBtn.innerText;
            tabPlacesBtn.innerText = "Finding Places...";
            tabPlacesBtn.disabled = true;

            const placesPanelElem = document.getElementById("placesPanel");
            if (placesPanelElem) {
                placesPanelElem.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }

            // Trigger discovery for current temple
            fetchNearbyPlaces(currentSelectedTemple, currentLat, currentLng, () => {
                tabPlacesBtn.innerText = originalText;
                tabPlacesBtn.disabled = false;
            });
        });
    }

    if (tabMapBtn) {
        tabMapBtn.addEventListener("click", () => {
            if (tabPlacesBtn) tabPlacesBtn.classList.remove("active");
            tabMapBtn.classList.add("active");
            if (googleMap) {
                google.maps.event.trigger(googleMap, "resize");
            }
        });
    }

    // -------------------------------------------------------------
    // Chat Submission & Orchestration
    // -------------------------------------------------------------
    window.sendPrompt = function(text) {
        userQuery.value = text;
        chatForm.dispatchEvent(new Event("submit"));
    };

    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        let question = userQuery.value.trim();
        if (!question) return;

        // Apply language directive if non-English chip active
        if (currentLang === "te" && !question.toLowerCase().includes("telugu")) {
            question = `Answer in Telugu: ${question}`;
        } else if (currentLang === "hi" && !question.toLowerCase().includes("hindi")) {
            question = `Answer in Hindi: ${question}`;
        }

        // Hide initial welcome box if present
        const welcomeBox = document.getElementById("welcomeBox");
        if (welcomeBox) welcomeBox.style.display = "none";

        // Append User Message Bubble
        appendUserMessage(question);
        userQuery.value = "";
        submitBtn.disabled = true;

        // Append Loading Indicator
        const loadingId = appendLoadingBubble();

        try {
            const chatHeaders = { "Content-Type": "application/json" };
            const storedJwt = localStorage.getItem("pilgrim_jwt");
            if (storedJwt) {
                chatHeaders["Authorization"] = `Bearer ${storedJwt}`;
            }

            const res = await fetch("/chat", {
                method: "POST",
                headers: chatHeaders,
                body: JSON.stringify({
                    question: question,
                    session_id: currentSessionId
                })
            });

            removeLoadingBubble(loadingId);

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                appendErrorMessage(errData.detail || "Server communication error. Please try again.");
                return;
            }

            const data = await res.json();
            
            // Preserve session_id from response
            if (data.session_id) {
                currentSessionId = data.session_id;
                localStorage.setItem("pilgrim_session_id", currentSessionId);
            }

            // Render structured bot response
            appendBotResponse(data);

            // Trigger Map / Places side-effects if applicable
            handleMapSideEffects(data);

        } catch (err) {
            removeLoadingBubble(loadingId);
            appendErrorMessage("Connection error. Ensure local PilgrimAI backend is running on http://localhost:8000.");
        } finally {
            submitBtn.disabled = false;
            scrollToBottom();
        }
    });

    // -------------------------------------------------------------
    // Message Rendering Helpers
    // -------------------------------------------------------------
    function appendUserMessage(text) {
        const row = document.createElement("div");
        row.className = "msg-row user";
        row.innerHTML = `
            <div class="msg-avatar">YOU</div>
            <div class="msg-bubble-wrapper">
                <div class="msg-bubble">${escapeHtml(text)}</div>
            </div>
        `;
        messageArea.appendChild(row);
        scrollToBottom();
    }

    function appendErrorMessage(errText) {
        const row = document.createElement("div");
        row.className = "msg-row bot";
        row.innerHTML = `
            <div class="msg-avatar" style="background: #ef4444; color: #fff;">⚠️</div>
            <div class="msg-bubble-wrapper">
                <div class="msg-bubble" style="border-color: #ef4444; color: #fca5a5;">
                    ${escapeHtml(errText)}
                </div>
            </div>
        `;
        messageArea.appendChild(row);
        scrollToBottom();
    }

    function appendLoadingBubble() {
        const id = "load_" + Date.now();
        const row = document.createElement("div");
        row.className = "msg-row bot";
        row.id = id;
        row.innerHTML = `
            <div class="msg-avatar">AI</div>
            <div class="msg-bubble-wrapper">
                <div class="msg-bubble" style="color: var(--text-muted); font-style: italic;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="dot-online" style="animation: pulse 1s infinite;"></span>
                        Consulting certified multi-agent engine...
                    </div>
                </div>
            </div>
        `;
        messageArea.appendChild(row);
        scrollToBottom();
        return id;
    }

    function removeLoadingBubble(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function appendBotResponse(data) {
        const row = document.createElement("div");
        row.className = "msg-row bot";

        // 1. Agent Name & Badge Mapping
        const badgeConfig = getAgentBadgeConfig(data.agent_name);
        const badgeHtml = `
            <div class="agent-badge-bar">
                <span class="agent-badge ${badgeConfig.className}">
                    ${badgeConfig.icon} ${badgeConfig.label}
                </span>
                ${data.latency_ms ? `<span class="latency-tag">${Math.round(data.latency_ms)}ms</span>` : ""}
                <div class="speech-controls" data-speech-state="idle">
                    ${renderSpeechControlsHtml("idle")}
                </div>
            </div>
        `;

        // 2. Structured Metadata Cards
        let structuredCardsHtml = "";
        const meta = data.metadata || {};

        // Weather Card
        if (data.agent_name === "live_weather" || meta.current_weather) {
            structuredCardsHtml += renderWeatherCard(meta);
        }
        // Budget Card
        else if (data.agent_name === "budget" || meta.calculated_total) {
            structuredCardsHtml += renderBudgetCard(meta);
        }
        // Navigation Card
        else if (data.agent_name === "live_navigation" || meta.distance_km !== undefined) {
            structuredCardsHtml += renderNavigationCard(meta);
        }
        // Itinerary Card
        else if (data.agent_name === "itinerary_planning" || meta.itinerary) {
            structuredCardsHtml += renderItineraryCard(meta);
        }

        // 3. Format Answer Markdown
        const formattedAnswer = formatMarkdownText(data.answer);

        // 4. Sources & Confidence Bar
        let sourcesHtml = "";
        if (data.sources && data.sources.length > 0) {
            const chips = data.sources.map(s => `<span class="src-chip">${escapeHtml(s)}</span>`).join("");
            let confHtml = "";
            if (data.confidence_score !== undefined && data.confidence_score > -900) {
                confHtml = `<span class="conf-chip">Confidence: ${data.confidence_score.toFixed(2)}</span>`;
            }
            sourcesHtml = `
                <div class="sources-bar">
                    <span>📄 Sources:</span>
                    ${chips}
                    ${confHtml}
                </div>
            `;
        }

        row.innerHTML = `
            <div class="msg-avatar">AI</div>
            <div class="msg-bubble-wrapper">
                ${badgeHtml}
                <div class="msg-bubble" data-raw-answer="${escapeHtml(data.answer)}">
                    ${structuredCardsHtml}
                    <div class="answer-content">${formattedAnswer}</div>
                    ${sourcesHtml}
                </div>
            </div>
        `;

        messageArea.appendChild(row);
        if (window.lucide) lucide.createIcons();
        scrollToBottom();
    }

    // -------------------------------------------------------------
    // Agent Badges Config
    // -------------------------------------------------------------
    function getAgentBadgeConfig(agentName) {
        switch (agentName) {
            case "temple_information":
                return { label: "Temple Information", icon: "🛕", className: "badge-temple_info" };
            case "comparison":
                return { label: "Temple Comparison", icon: "⚖️", className: "badge-comparison" };
            case "cross_temple_aggregation":
                return { label: "Cross-Temple Search", icon: "🔍", className: "badge-temple_info" };
            case "itinerary_planning":
                return { label: "Itinerary Planner", icon: "📅", className: "badge-itinerary" };
            case "live_weather":
                return { label: "Live Weather", icon: "🌤️", className: "badge-weather" };
            case "budget":
                return { label: "Budget Specialist", icon: "💰", className: "badge-budget" };
            case "live_navigation":
                return { label: "Live Navigation", icon: "🧭", className: "badge-navigation" };
            case "voice_multilingual":
                return { label: "Multilingual Guide", icon: "🌐", className: "badge-multilingual" };
            case "emergency":
                return { label: "Emergency Services", icon: "🚨", className: "badge-emergency" };
            case "recommendation":
                return { label: "Temple Recommendation", icon: "⭐", className: "badge-temple_info" };
            case "multi_intent":
                return { label: "Multi-Intent Pipeline", icon: "⚡", className: "badge-comparison" };
            default:
                return { label: agentName ? agentName.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()) : "Pilgrim Specialist", icon: "✨", className: "badge-default" };
        }
    }

    // -------------------------------------------------------------
    // Structured Card Renderers
    // -------------------------------------------------------------
    function renderWeatherCard(meta) {
        const cur = meta.current_weather || {};
        const temp = cur.temperature !== undefined ? `${cur.temperature}°C` : "N/A";
        const cond = cur.condition || "Live Observation";
        const loc = meta.display_name || meta.location || "Temple Region";
        const humidity = cur.relative_humidity !== undefined ? `${cur.relative_humidity}%` : "--";
        const wind = cur.wind_speed !== undefined ? `${cur.wind_speed} km/h` : "--";
        const rain = cur.precipitation !== undefined ? `${cur.precipitation} mm` : "--";
        const cacheTag = meta.cache_hit ? "Cached" : "Fresh";

        return `
            <div class="structured-card weather-card">
                <div class="weather-header">
                    <div>
                        <div class="weather-loc">🌤️ ${escapeHtml(loc)}</div>
                        <div style="font-size: 11.5px; color: var(--text-secondary);">${escapeHtml(cond)} • <span style="color: var(--accent-emerald);">${cacheTag}</span></div>
                    </div>
                    <div class="weather-temp-badge">${temp}</div>
                </div>
                <div class="weather-grid">
                    <div class="weather-metric">
                        <div class="label">Humidity</div>
                        <div class="val">${humidity}</div>
                    </div>
                    <div class="weather-metric">
                        <div class="label">Wind Speed</div>
                        <div class="val">${wind}</div>
                    </div>
                    <div class="weather-metric">
                        <div class="label">Rain</div>
                        <div class="val">${rain}</div>
                    </div>
                </div>
            </div>
        `;
    }

    function renderBudgetCard(meta) {
        const total = meta.calculated_total || {};
        let totalStr = "₹0";
        const isZeroCost = (total.min === 0 && total.max === 0) || (total.min === undefined && total.max === undefined);
        if (total.min !== undefined && total.max !== undefined) {
            totalStr = total.min === total.max 
                ? `₹${total.min.toLocaleString()}` 
                : `₹${total.min.toLocaleString()} – ₹${total.max.toLocaleString()}`;
        }
        const pax = meta.parameters ? meta.parameters.pax : 1;
        const verifiedCount = meta.verified_item_count || 0;
        const costLabel = isZeroCost ? "Temple Entry & Darshan (Free)" : "Verified Entry / Darshan / Seva Cost";

        return `
            <div class="structured-card budget-card">
                <div class="budget-total-bar">
                    <div>
                        <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">${costLabel}</div>
                        <div class="budget-total-val">${totalStr}</div>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 11px; background: rgba(16, 185, 129, 0.15); color: var(--accent-emerald); padding: 2px 8px; border-radius: 12px; font-weight: 600;">
                            ${verifiedCount} Verified Tariff(s)
                        </span>
                    </div>
                </div>
                <div class="budget-tags">
                    <span>👥 Group: ${pax} Pilgrim(s)</span>
                    <span>•</span>
                    <span>${isZeroCost ? "General entry is free; optional special sevas/transport extra" : "Static verified temple records"}</span>
                </div>
            </div>
        `;
    }

    function renderNavigationCard(meta) {
        const orig = meta.origin || "Origin";
        const dest = meta.destination || "Destination";
        const origCanon = meta.origin_canonical || "";
        const destCanon = meta.destination_canonical || "";
        const dist = meta.distance_km !== null && meta.distance_km !== undefined ? `${meta.distance_km} km` : "N/A";
        const dur = meta.duration_minutes !== null && meta.duration_minutes !== undefined ? `${Math.round(meta.duration_minutes)} min` : "N/A";
        const traffic = meta.traffic_duration_minutes !== null && meta.traffic_duration_minutes !== undefined 
            ? `${Math.round(meta.traffic_duration_minutes)} min (traffic)` 
            : null;

        const safeOrig = escapeHtml(orig).replace(/'/g, "\\'");
        const safeDest = escapeHtml(dest).replace(/'/g, "\\'");
        const safeOrigCanon = escapeHtml(origCanon).replace(/'/g, "\\'");
        const safeDestCanon = escapeHtml(destCanon).replace(/'/g, "\\'");

        return `
            <div class="structured-card nav-card">
                <div class="nav-route-row">
                    <span>🧭</span>
                    <span>${escapeHtml(orig)}</span>
                    <span style="color: var(--accent-gold);">➔</span>
                    <span>${escapeHtml(dest)}</span>
                </div>
                <div class="nav-metrics">
                    <div class="nav-metric-item"><strong>Distance:</strong> ${dist}</div>
                    <div class="nav-metric-item"><strong>Duration:</strong> ${dur}</div>
                    ${traffic ? `<div class="nav-metric-item" style="color: var(--accent-gold);"><strong>Live Traffic:</strong> ${traffic}</div>` : ""}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                    <span style="font-size: 10.5px; color: var(--text-muted);">Source: Google Maps Routes API</span>
                    <button class="nav-btn-view-map" 
                            id="viewRouteBtn"
                            data-origin="${escapeHtml(orig)}" 
                            data-destination="${escapeHtml(dest)}" 
                            data-origin-canonical="${escapeHtml(origCanon)}" 
                            data-destination-canonical="${escapeHtml(destCanon)}"
                            onclick="handleViewRouteClick(this, '${safeOrig}', '${safeDest}', '${safeOrigCanon}', '${safeDestCanon}')">
                        🗺️ View Route on Map
                    </button>
                </div>
            </div>
        `;
    }

    function renderItineraryCard(meta) {
        const temples = meta.temples || [];
        const days = meta.duration_days || 1;
        const templePills = temples.map(t => `<span class="src-chip" style="background: rgba(244, 63, 94, 0.15); color: #fda4af;">${escapeHtml(t)}</span>`).join(" ");

        return `
            <div class="structured-card" style="border-color: rgba(244, 63, 94, 0.3); background: linear-gradient(135deg, rgba(136, 19, 55, 0.2), rgba(15, 23, 42, 0.8));">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-weight: 700; color: #fff; font-size: 13.5px;">📅 ${days} Day Pilgrimage Schedule</span>
                    <span style="font-size: 10.5px; color: var(--accent-gold);">Verified Temples</span>
                </div>
                <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                    ${templePills}
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------
    // Route Visualization & Location Resolution
    // -------------------------------------------------------------
    const KNOWN_REGIONAL_COORDINATES = {
        "hyderabad": { lat: 17.385044, lng: 78.486671, name: "Hyderabad" },
        "secunderabad": { lat: 17.4399, lng: 78.4983, name: "Secunderabad" },
        "warangal": { lat: 17.9689, lng: 79.5941, name: "Warangal" },
        "karimnagar": { lat: 18.4386, lng: 79.1288, name: "Karimnagar" },
        "nizamabad": { lat: 18.6725, lng: 78.0941, name: "Nizamabad" },
        "khammam": { lat: 17.2473, lng: 80.1514, name: "Khammam" },
        "nalgonda": { lat: 17.0575, lng: 79.2684, name: "Nalgonda" },
        "suryapet": { lat: 17.1439, lng: 79.6239, name: "Suryapet" },
        "mahabubnagar": { lat: 16.7488, lng: 77.9856, name: "Mahabubnagar" },
        "siddipet": { lat: 18.1018, lng: 78.8520, name: "Siddipet" },
        "ramagundam": { lat: 18.7551, lng: 79.5133, name: "Ramagundam" },
        "mancherial": { lat: 18.8679, lng: 79.4639, name: "Mancherial" },
        "vijayawada": { lat: 16.5062, lng: 80.6480, name: "Vijayawada" },
        "guntur": { lat: 16.3067, lng: 80.4365, name: "Guntur" },
        "visakhapatnam": { lat: 17.6868, lng: 83.2185, name: "Visakhapatnam" },
        "tirupati": { lat: 13.6288, lng: 79.4192, name: "Tirupati" },
        "kurnool": { lat: 15.8281, lng: 78.0373, name: "Kurnool" },
        "bengaluru": { lat: 12.9716, lng: 77.5946, name: "Bengaluru" },
        "bangalore": { lat: 12.9716, lng: 77.5946, name: "Bengaluru" },
        "chennai": { lat: 13.0827, lng: 80.2707, name: "Chennai" },
        "mumbai": { lat: 19.0760, lng: 72.8777, name: "Mumbai" },
        "delhi": { lat: 28.6139, lng: 77.2090, name: "Delhi" },
        "pune": { lat: 18.5204, lng: 73.8567, name: "Pune" }
    };

    const CANONICAL_TEMPLE_ALIASES = {
        "vemulawada": "Vemulavada",
        "vemulavada": "Vemulavada",
        "rajarajeshwara": "Vemulavada",
        "rajanna": "Vemulavada",
        "yadagiri": "Yadadri",
        "yadagirigutta": "Yadadri",
        "yadadri": "Yadadri",
        "basar": "Basara",
        "basara": "Basara",
        "gnana saraswathi": "Basara",
        "dharmapuri": "Dharmapuri",
        "bhadrachalam": "Badrachalam",
        "badrachalam": "Badrachalam",
        "srisailam": "Srisaila",
        "srisaila": "Srisaila"
    };

    function resolveLocationForMap(locationStr, canonicalHint) {
        if (!locationStr && !canonicalHint) return null;
        if (typeof locationStr === "object" && locationStr.lat && locationStr.lng) {
            return locationStr;
        }

        const raw = String(locationStr || "").trim();
        const clean = raw.toLowerCase().replace(/^(the|a|an)\s+/i, "").replace(/[?!.,;]+$/, "").trim();
        const canonClean = String(canonicalHint || "").toLowerCase().trim();

        // 1. Check canonicalHint in verified templeCoordinates (Priority 1)
        if (canonClean && Array.isArray(templeCoordinates) && templeCoordinates.length > 0) {
            const foundCanon = templeCoordinates.find(t => t.canonical_name && t.canonical_name.toLowerCase() === canonClean);
            if (foundCanon) {
                return { lat: foundCanon.latitude, lng: foundCanon.longitude, name: foundCanon.display_name, isTemple: true };
            }
        }

        // 2. Check alias map
        for (const [alias, canonicalTarget] of Object.entries(CANONICAL_TEMPLE_ALIASES)) {
            if (clean === alias || clean.includes(alias)) {
                const found = templeCoordinates.find(t => t.canonical_name && t.canonical_name.toLowerCase() === canonicalTarget.toLowerCase());
                if (found) {
                    return { lat: found.latitude, lng: found.longitude, name: found.display_name, isTemple: true };
                }
            }
        }

        // 3. Check clean in verified templeCoordinates (Priority 2)
        if (Array.isArray(templeCoordinates) && templeCoordinates.length > 0) {
            // A. Exact canonical_name
            let found = templeCoordinates.find(t => t.canonical_name && t.canonical_name.toLowerCase() === clean);
            if (found) return { lat: found.latitude, lng: found.longitude, name: found.display_name, isTemple: true };

            // B. Exact display_name
            found = templeCoordinates.find(t => t.display_name && t.display_name.toLowerCase() === clean);
            if (found) return { lat: found.latitude, lng: found.longitude, name: found.display_name, isTemple: true };

            // C. Substring/containment match
            found = templeCoordinates.find(t => {
                const c = (t.canonical_name || "").toLowerCase();
                const d = (t.display_name || "").toLowerCase();
                return (c && clean.includes(c)) || (c && c.includes(clean)) || (d && clean.includes(d)) || (d && d.includes(clean));
            });
            if (found) return { lat: found.latitude, lng: found.longitude, name: found.display_name, isTemple: true };
        }

        // 4. Check known regional cities (Priority 3)
        if (KNOWN_REGIONAL_COORDINATES[clean]) {
            const city = KNOWN_REGIONAL_COORDINATES[clean];
            return { lat: city.lat, lng: city.lng, name: city.name, isTemple: false };
        }
        for (const [key, city] of Object.entries(KNOWN_REGIONAL_COORDINATES)) {
            if (clean.includes(key)) {
                return { lat: city.lat, lng: city.lng, name: city.name, isTemple: false };
            }
        }

        // 5. Fallback: string for DirectionsService geocoding
        return clean.includes("telangana") || clean.includes("india") ? raw : `${raw}, Telangana, India`;
    }

    function decodePolyline(encoded) {
        if (!encoded) return [];
        let points = [];
        let index = 0, len = encoded.length;
        let lat = 0, lng = 0;
        while (index < len) {
            let b, shift = 0, result = 0;
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);
            let dlat = ((result & 1) ? ~(result >> 1) : (result >> 1));
            lat += dlat;
            shift = 0;
            result = 0;
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);
            let dlng = ((result & 1) ? ~(result >> 1) : (result >> 1));
            lng += dlng;
            points.push({ lat: lat / 1e5, lng: lng / 1e5 });
        }
        return points;
    }

    function clearActiveRoute() {
        try {
            if (directionsRenderer) {
                directionsRenderer.setMap(null);
                directionsRenderer = null;
            }
        } catch (e) {
            console.warn("[PilgrimAI Routes Diagnostics] clearActiveRoute error:", e);
        }
        try {
            if (activeRoutePolyline) {
                activeRoutePolyline.setMap(null);
                activeRoutePolyline = null;
            }
        } catch (e) {}
        try {
            if (Array.isArray(activeRouteMarkers)) {
                activeRouteMarkers.forEach(m => {
                    try { m.setMap(null); } catch (e) {}
                });
                activeRouteMarkers = [];
            }
        } catch (e) {}
    }

    function formatRoutesWaypoint(resolved) {
        if (!resolved) return null;
        if (typeof resolved === "object" && resolved.lat !== undefined && resolved.lng !== undefined) {
            return {
                location: {
                    lat: Number(resolved.lat),
                    lng: Number(resolved.lng)
                }
            };
        }
        if (typeof resolved === "string" && resolved.trim()) {
            return {
                address: resolved.trim()
            };
        }
        if (typeof resolved === "object" && resolved.name) {
            return {
                address: String(resolved.name).trim()
            };
        }
        return null;
    }

    async function tryModernRoutesCompute(origResolved, destResolved) {
        if (!window.google || !google.maps || typeof google.maps.importLibrary !== "function") {
            return null;
        }
        try {
            const routePromise = (async () => {
                try {
                    const { Route } = await google.maps.importLibrary("routes");
                    if (!Route || typeof Route.computeRoutes !== "function") return null;

                    const originWaypoint = formatRoutesWaypoint(origResolved);
                    const destWaypoint = formatRoutesWaypoint(destResolved);

                    if (!originWaypoint || !destWaypoint) return null;

                    const request = {
                        origin: originWaypoint,
                        destination: destWaypoint,
                        travelMode: "DRIVING",
                        fields: [
                            "routes.distanceMeters",
                            "routes.duration",
                            "routes.polyline.encodedPolyline",
                            "routes.viewport"
                        ]
                    };

                    const res = await Route.computeRoutes(request);

                    if (res && res.routes && res.routes.length > 0) {
                        const primary = res.routes[0];
                        const encoded = primary.polyline && primary.polyline.encodedPolyline;
                        if (encoded) {
                            const path = decodePolyline(encoded);
                            if (path && path.length > 0) {
                                return {
                                    path,
                                    viewport: primary.viewport,
                                    distanceMeters: primary.distanceMeters,
                                    duration: primary.duration
                                };
                            }
                        }
                    }
                    return null;
                } catch (innerErr) {
                    console.warn("[PilgrimAI Routes Diagnostics] Modern Route.computeRoutes error:", innerErr.message || innerErr);
                    return null;
                }
            })();

            return await Promise.race([
                routePromise,
                new Promise(resolve => setTimeout(() => resolve(null), 8000))
            ]);
        } catch (e) {
            console.warn("[PilgrimAI Routes Diagnostics] Modern Route.computeRoutes failed:", e.message || e);
        }
        return null;
    }

    function renderModernPolylineRoute(routeData, origResolved, destResolved) {
        clearActiveRoute();

        activeRoutePolyline = new google.maps.Polyline({
            path: routeData.path,
            geodesic: true,
            strokeColor: "#fbbf24",
            strokeOpacity: 0.85,
            strokeWeight: 6,
            map: googleMap
        });

        // Fit bounds across all points
        const bounds = new google.maps.LatLngBounds();
        routeData.path.forEach(pt => bounds.extend(pt));
        googleMap.fitBounds(bounds);

        activeRouteMarkers = [];

        // Origin and Destination Markers
        const startPos = (origResolved && typeof origResolved === "object" && origResolved.lat !== undefined)
            ? { lat: Number(origResolved.lat), lng: Number(origResolved.lng) }
            : (routeData.path && routeData.path.length > 0 ? routeData.path[0] : null);

        const endPos = (destResolved && typeof destResolved === "object" && destResolved.lat !== undefined)
            ? { lat: Number(destResolved.lat), lng: Number(destResolved.lng) }
            : (routeData.path && routeData.path.length > 0 ? routeData.path[routeData.path.length - 1] : null);

        if (startPos) {
            const startMarker = new google.maps.Marker({
                position: startPos,
                map: googleMap,
                title: (origResolved && origResolved.name) || "Origin",
                label: { text: "A", color: "#fff", fontWeight: "bold" },
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 8,
                    fillColor: "#3b82f6",
                    fillOpacity: 1,
                    strokeColor: "#ffffff",
                    strokeWeight: 2
                }
            });
            activeRouteMarkers.push(startMarker);
        }

        if (endPos) {
            const endMarker = new google.maps.Marker({
                position: endPos,
                map: googleMap,
                title: (destResolved && destResolved.name) || "Destination",
                label: { text: "B", color: "#fff", fontWeight: "bold" },
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 8,
                    fillColor: "#10b981",
                    fillOpacity: 1,
                    strokeColor: "#ffffff",
                    strokeWeight: 2
                }
            });
            activeRouteMarkers.push(endMarker);
        }

        highlightDestinationTemple(destResolved);
        return true;
    }

    function highlightDestinationTemple(destResolved) {
        if (!destResolved || !destResolved.isTemple) return;
        const match = templeCoordinates.find(t => 
            (destResolved.name && t.display_name === destResolved.name) ||
            (destResolved.lat && Math.abs(t.latitude - destResolved.lat) < 0.001 && Math.abs(t.longitude - destResolved.lng) < 0.001)
        );
        if (match) {
            currentSelectedTemple = match.display_name;
            currentLat = match.latitude;
            currentLng = match.longitude;
        }
    }

    // -------------------------------------------------------------
    // Map & Route Side-Effects
    // -------------------------------------------------------------
    function handleMapSideEffects(data) {
        const meta = data.metadata || {};

        // 1. Navigation query: highlight route
        if (data.agent_name === "live_navigation" || meta.distance_km !== undefined) {
            if (meta.origin && meta.destination) {
                setTimeout(() => {
                    const btn = document.getElementById("viewRouteBtn");
                    focusRouteOnMap(meta.origin, meta.destination, btn, meta.origin_canonical, meta.destination_canonical);
                }, 50);
            }
        }

        // 2. Weather query: pan to temple
        if (data.agent_name === "live_weather" && meta.latitude && meta.longitude) {
            currentSelectedTemple = meta.display_name || meta.location || currentSelectedTemple;
            currentLat = parseFloat(meta.latitude);
            currentLng = parseFloat(meta.longitude);
            panToCoordinates(meta.latitude, meta.longitude, meta.display_name || meta.location);
            fetchNearbyPlaces(meta.display_name || meta.location, meta.latitude, meta.longitude);
        }

        // 3. Temple Information query: focus on temple pin
        if (meta.detected_temple) {
            const found = templeCoordinates.find(t => t.canonical_name.toLowerCase() === meta.detected_temple.toLowerCase());
            if (found) {
                currentSelectedTemple = found.display_name;
                currentLat = found.latitude;
                currentLng = found.longitude;
                panToCoordinates(found.latitude, found.longitude, found.display_name);
                fetchNearbyPlaces(found.display_name, found.latitude, found.longitude);
            }
        }
    }

    window.focusRouteOnMap = async function(origin, destination, btn, originCanonical, destCanonical) {
        if (!origin || !destination) {
            console.warn("[PilgrimAI Routes Diagnostics] focusRouteOnMap called without origin or destination", { origin, destination });
            return false;
        }

        // Failure 1: Map unavailable
        if (!googleMap) {
            console.warn("[PilgrimAI Routes Diagnostics] [Failure 1: Map unavailable] Google Map instance not initialized yet.");
            return false;
        }

        // 1. Ensure map panel is open and visible
        if (mapPanel && mapPanel.classList.contains("collapsed")) {
            mapPanel.classList.remove("collapsed");
        }
        if (tabMapBtn && !tabMapBtn.classList.contains("active")) {
            tabMapBtn.classList.add("active");
            if (tabPlacesBtn) tabPlacesBtn.classList.remove("active");
        }
        google.maps.event.trigger(googleMap, "resize");

        // 2. Clear any previously displayed route (single active route visualization)
        clearActiveRoute();

        // 3. Resolve origin and destination
        const origResolved = resolveLocationForMap(origin, originCanonical);
        const destResolved = resolveLocationForMap(destination, destCanonical);

        // Failure 2: Origin coordinates unavailable
        if (!origResolved) {
            console.warn("[PilgrimAI Routes Diagnostics] [Failure 2: Origin coordinates unavailable] Unable to resolve coordinates for origin: " + origin);
            return false;
        }

        // Failure 3: Destination coordinates unavailable
        if (!destResolved) {
            console.warn("[PilgrimAI Routes Diagnostics] [Failure 3: Destination coordinates unavailable] Unable to resolve coordinates for destination: " + destination);
            return false;
        }

        // 4. Try modern Route.computeRoutes first if available (strict 300ms timeout)
        const modernRoute = await tryModernRoutesCompute(origResolved, destResolved);
        if (modernRoute) {
            // Failure 6: Route geometry unavailable check
            if (!modernRoute.path || modernRoute.path.length === 0) {
                console.warn("[PilgrimAI Routes Diagnostics] [Failure 6: Route geometry unavailable] Modern routes returned no polyline points.");
            } else {
                const rendered = renderModernPolylineRoute(modernRoute, origResolved, destResolved);
                if (rendered) {
                    if (btn) {
                        btn.classList.add("success");
                        btn.innerText = "✓ Route shown on map";
                        setTimeout(() => {
                            btn.classList.remove("success");
                            btn.innerText = "🗺️ View Route on Map";
                        }, 4000);
                    }
                    return true;
                }
            }
        }

        // 5. DirectionsService & DirectionsRenderer fallback
        return new Promise((resolve) => {
            try {
                // Failure 4: Routes JS API unavailable
                if (!window.google || !google.maps) {
                    console.warn("[PilgrimAI Routes Diagnostics] [Failure 4: Routes JS API unavailable] Google Maps JavaScript API is not loaded.");
                    resolve(false);
                    return;
                }

                if (!directionsService) {
                    directionsService = new google.maps.DirectionsService();
                }
                if (!directionsRenderer) {
                    directionsRenderer = new google.maps.DirectionsRenderer({
                        map: googleMap,
                        suppressMarkers: false,
                        polylineOptions: {
                            strokeColor: "#fbbf24",
                            strokeWeight: 6,
                            strokeOpacity: 0.9
                        }
                    });
                }
                directionsRenderer.setMap(googleMap);

                const origWaypoint = (typeof origResolved === "object" && origResolved.lat && origResolved.lng)
                    ? new google.maps.LatLng(origResolved.lat, origResolved.lng)
                    : origResolved;
                const destWaypoint = (typeof destResolved === "object" && destResolved.lat && destResolved.lng)
                    ? new google.maps.LatLng(destResolved.lat, destResolved.lng)
                    : destResolved;

                directionsService.route({
                    origin: origWaypoint,
                    destination: destWaypoint,
                    travelMode: google.maps.TravelMode.DRIVING
                }, (result, status) => {
                    if (status === google.maps.DirectionsStatus.OK && result) {
                        // Failure 6 check: geometry check
                        if (!result.routes || result.routes.length === 0 || !result.routes[0].overview_path || result.routes[0].overview_path.length === 0) {
                            console.warn("[PilgrimAI Routes Diagnostics] [Failure 6: Route geometry unavailable] DirectionsService returned OK but empty overview_path.");
                            resolve(false);
                            return;
                        }

                        directionsRenderer.setDirections(result);

                        // Fit bounds to entire route
                        if (result.routes[0].bounds) {
                            googleMap.fitBounds(result.routes[0].bounds);
                        }

                        // Keep destination temple marker visible
                        highlightDestinationTemple(destResolved);

                        if (btn) {
                            btn.classList.add("success");
                            btn.innerText = "✓ Route shown on map";
                            setTimeout(() => {
                                btn.classList.remove("success");
                                btn.innerText = "🗺️ View Route on Map";
                            }, 4000);
                        }
                        resolve(true);
                    } else {
                        // Failure 5: Route calculation rejected (e.g. REQUEST_DENIED due to key restrictions)
                        console.warn("[PilgrimAI Routes Diagnostics] [Failure 5: Route calculation rejected] DirectionsService status: " + status + ". (Browser key lacks Directions API / Routes API capability in Google Cloud API restrictions)");
                        resolve(false);
                    }
                });
            } catch (err) {
                // Failure 7: Route rendering failed
                console.error("[PilgrimAI Routes Diagnostics] [Failure 7: Route rendering failed] DirectionsService execution error: " + (err.message || err));
                resolve(false);
            }
        });
    };

    window.handleViewRouteClick = async function(btn, orig, dest, origCanon, destCanon) {
        if (!orig || !dest) {
            orig = orig || (btn && btn.dataset && btn.dataset.origin);
            dest = dest || (btn && btn.dataset && btn.dataset.destination);
            origCanon = origCanon || (btn && btn.dataset && btn.dataset.originCanonical);
            destCanon = destCanon || (btn && btn.dataset && btn.dataset.destinationCanonical);
        }

        if (!orig || !dest) {
            if (btn) btn.innerText = "Route coordinates missing";
            return;
        }

        const originalText = "🗺️ View Route on Map";
        if (btn) {
            btn.disabled = true;
            btn.classList.add("loading");
            btn.innerText = "Loading route...";
        }

        try {
            const success = await focusRouteOnMap(orig, dest, btn, origCanon, destCanon);
            if (btn) {
                btn.disabled = false;
                btn.classList.remove("loading");
                if (success) {
                    btn.classList.add("success");
                    btn.innerText = "✓ Route shown on map";
                    setTimeout(() => {
                        btn.classList.remove("success");
                        btn.innerText = originalText;
                    }, 4000);
                } else {
                    btn.classList.add("error");
                    btn.innerText = "Unable to display this route on the map.";
                    setTimeout(() => {
                        btn.classList.remove("error");
                        btn.innerText = originalText;
                    }, 4000);
                }
            }
        } catch (err) {
            console.error("[PilgrimAI Routes Diagnostics] handleViewRouteClick caught error:", err);
            if (btn) {
                btn.disabled = false;
                btn.classList.remove("loading");
                btn.classList.add("error");
                btn.innerText = "Unable to display this route on the map.";
                setTimeout(() => {
                    btn.classList.remove("error");
                    btn.innerText = originalText;
                }, 4000);
            }
        }
    };

    function panToCoordinates(lat, lng, title) {
        if (!googleMap) return;
        const pos = { lat: parseFloat(lat), lng: parseFloat(lng) };
        googleMap.panTo(pos);
        googleMap.setZoom(13);
    }

    // -------------------------------------------------------------
    // Google Maps JavaScript API Loader
    // -------------------------------------------------------------
    async function initGoogleMaps() {
        try {
            const res = await fetch("/api/maps/config");
            if (!res.ok) {
                showMapFallback();
                return;
            }
            const config = await res.json();
            if (!config.enabled || !config.api_key) {
                showMapFallback();
                return;
            }

            // Expose global callback
            window.initGoogleMap = onGoogleMapsLoaded;

            // Handle potential auth failure gracefully
            window.gm_authFailure = function() {
                console.warn("Google Maps JavaScript API authentication failed. Check referrer/API restrictions.");
                showMapFallback();
            };

            const script = document.createElement("script");
            script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(config.api_key)}&libraries=places&callback=initGoogleMap`;
            script.async = true;
            script.defer = true;
            script.onerror = () => {
                showMapFallback();
            };
            document.head.appendChild(script);

        } catch (e) {
            showMapFallback();
        }
    }

    function showMapFallback() {
        if (mapFallback) {
            mapFallback.style.display = "flex";
        }
    }

    function onGoogleMapsLoaded() {
        const container = document.getElementById("googleMapContainer");
        if (!container) return;

        // Center on Telangana geographic centroid
        const telanganaCenter = { lat: 17.8495, lng: 79.1151 };

        googleMap = new google.maps.Map(container, {
            center: telanganaCenter,
            zoom: 7,
            mapId: "PILGRIM_AI_MAP",
            disableDefaultUI: false,
            zoomControl: true,
            styles: [
                { elementType: "geometry", stylers: [{ color: "#17263c" }] },
                { elementType: "labels.text.stroke", stylers: [{ color: "#242f3e" }] },
                { elementType: "labels.text.fill", stylers: [{ color: "#746855" }] },
                { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#d59563" }] },
                { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#d59563" }] },
                { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#263c3f" }] },
                { featureType: "road", elementType: "geometry", stylers: [{ color: "#38414e" }] },
                { featureType: "water", elementType: "geometry", stylers: [{ color: "#17263c" }] }
            ]
        });

        directionsService = new google.maps.DirectionsService();
        directionsRenderer = new google.maps.DirectionsRenderer({
            map: googleMap,
            suppressMarkers: false,
            polylineOptions: {
                strokeColor: "#fbbf24",
                strokeWeight: 5,
                strokeOpacity: 0.8
            }
        });

        // Load 20 temple coordinates from backend registry
        loadTemplePins();
    }

    async function loadTemplePins() {
        try {
            const res = await fetch("/api/maps/temples");
            if (!res.ok) return;
            templeCoordinates = await res.json();

            // Populate temple markers
            templeCoordinates.forEach(t => {
                const marker = new google.maps.Marker({
                    position: { lat: t.latitude, lng: t.longitude },
                    map: googleMap,
                    title: t.display_name,
                    icon: {
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 7,
                        fillColor: "#fbbf24",
                        fillOpacity: 1,
                        strokeColor: "#000",
                        strokeWeight: 2
                    }
                });

                const infoWindow = new google.maps.InfoWindow({
                    content: `
                        <div style="color: #000; padding: 6px; font-family: sans-serif;">
                            <strong style="font-size: 14px;">${escapeHtml(t.display_name)}</strong><br>
                            <span style="font-size: 12px; color: #555;">District: ${escapeHtml(t.district)}, ${escapeHtml(t.state)}</span><br>
                            <div style="margin-top: 6px;">
                                <button onclick="discoverPlacesForTemple('${escapeHtml(t.display_name)}', ${t.latitude}, ${t.longitude})" style="background: #fbbf24; border: none; padding: 4px 8px; border-radius: 4px; font-weight: 600; cursor: pointer;">
                                    Find Nearby Places
                                </button>
                            </div>
                        </div>
                    `
                });

                marker.addListener("click", () => {
                    infoWindow.open(googleMap, marker);
                    fetchNearbyPlaces(t.display_name, t.latitude, t.longitude);
                });

                mapMarkers.push(marker);
            });

        } catch (e) {
            console.warn("Could not load temple pins:", e);
        }
    }

    // -------------------------------------------------------------
    // Google Places API Discovery (Segregated & Safe)
    // -------------------------------------------------------------
    window.discoverPlacesForTemple = function(name, lat, lng) {
        fetchNearbyPlaces(name, lat, lng);
    };

    // -------------------------------------------------------------
    // Google Places API Discovery (Browser-Side & Safe)
    // -------------------------------------------------------------
    window.discoverPlacesForTemple = function(name, lat, lng) {
        fetchNearbyPlaces(name, lat, lng);
    };

    window.getPlacesDiagnostics = function() {
        const googleLoaded = typeof window.google !== "undefined";
        const mapsLoaded = !!(googleLoaded && window.google.maps);
        const placesLibraryLoaded = !!(mapsLoaded && window.google.maps.places);
        const placesServiceAvailable = !!(placesLibraryLoaded && window.google.maps.places.PlacesService);

        return {
            googleLoaded: googleLoaded,
            mapsLoaded: mapsLoaded,
            placesLibraryLoaded: placesLibraryLoaded,
            placesServiceAvailable: placesServiceAvailable,
            selectedTemple: currentSelectedTemple,
            selectedLatitude: currentLat,
            selectedLongitude: currentLng,
            latitude: currentLat,
            longitude: currentLng,
            requestStarted: placesRequestStarted,
            lastStatus: placesLastStatus,
            lastResultCount: placesLastResultCount,
            resultsCount: placesLastResultCount,
            lastError: placesLastError
        };
    };

    function fetchNearbyPlaces(templeName, lat, lng, onComplete) {
        placesRequestStarted = true;

        if (!templeName) templeName = currentSelectedTemple || "Sri Lakshmi Narasimha Swamy Temple, Yadadri";

        const finish = (status, count, err) => {
            placesLastStatus = status;
            placesLastResultCount = count || 0;
            placesLastError = err || null;
            if (typeof onComplete === "function") {
                try { onComplete(); } catch (e) {}
            }
        };

        let parsedLat = parseFloat(lat);
        let parsedLng = parseFloat(lng);

        if (lat === undefined || lat === null || lat === "") {
            parsedLat = parseFloat(currentLat);
        }
        if (lng === undefined || lng === null || lng === "") {
            parsedLng = parseFloat(currentLng);
        }

        // Validate Coordinates (-90 to 90 for lat, -180 to 180 for lng)
        if (isNaN(parsedLat) || isNaN(parsedLng) || parsedLat < -90 || parsedLat > 90 || parsedLng < -180 || parsedLng > 180) {
            const err = "Selected temple does not have valid geographic coordinates.";
            finish("INVALID_COORDINATES", 0, err);
            renderPlacesError("Invalid Coordinates", err);
            return;
        }

        currentSelectedTemple = templeName;
        currentLat = parsedLat;
        currentLng = parsedLng;

        if (placesTargetTitle) {
            placesTargetTitle.innerText = `Places near ${templeName}`;
        }
        if (placesList) {
            placesList.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 14px;">Searching live Google Places for hotels & restaurants near ${escapeHtml(templeName)}...</div>`;
        }

        const googleLoaded = typeof window.google !== "undefined";
        const mapsLoaded = !!(googleLoaded && window.google.maps);
        const placesLibraryLoaded = !!(mapsLoaded && window.google.maps.places);
        const placesServiceAvailable = !!(placesLibraryLoaded && window.google.maps.places.PlacesService);

        // PRIMARY PATH: Browser-side PlacesService using browser HTTP referrer restricted key
        if (placesServiceAvailable) {
            try {
                const mapContainer = googleMap || document.getElementById("googleMapContainer") || document.createElement("div");
                const service = new google.maps.places.PlacesService(mapContainer);
                const pos = new google.maps.LatLng(currentLat, currentLng);
                const request = {
                    location: pos,
                    radius: 5000,
                    keyword: "hotels and restaurants"
                };

                service.nearbySearch(request, (results, status) => {
                    const statusStr = String(status);
                    console.log(`Places status: ${statusStr}, results count: ${results ? results.length : 0}, selected temple: ${templeName}, coordinates: (${currentLat}, ${currentLng})`);

                    if (status === google.maps.places.PlacesServiceStatus.OK && results && results.length > 0) {
                        finish("OK", results.length, null);
                        renderPlacesResults(results.map(r => ({
                            name: r.name || "Unknown Place",
                            address: r.vicinity || r.formatted_address || "Address unavailable",
                            rating: r.rating,
                            user_ratings_total: r.user_ratings_total,
                            open_now: r.opening_hours ? r.opening_hours.isOpen() : null
                        })));
                    } else if (status === google.maps.places.PlacesServiceStatus.ZERO_RESULTS || (status === google.maps.places.PlacesServiceStatus.OK && (!results || results.length === 0))) {
                        finish("ZERO_RESULTS", 0, null);
                        renderPlacesZeroResults(`No nearby places were found within 5 km of ${escapeHtml(templeName)}.`);
                    } else if (status === google.maps.places.PlacesServiceStatus.REQUEST_DENIED) {
                        const errMsg = "Google Places access was denied. Check that the Places API is enabled for the browser API key in Google Cloud Console.";
                        finish("REQUEST_DENIED", 0, errMsg);
                        renderPlacesError("Google Places Access Denied (REQUEST_DENIED)", errMsg, "In Google Cloud Console under 'APIs & Services > Credentials', verify that your API key's API Restrictions include 'Places API' (in addition to 'Maps JavaScript API').");
                    } else if (status === google.maps.places.PlacesServiceStatus.OVER_QUERY_LIMIT) {
                        const errMsg = "Google Places request quota has been reached. Please try again later.";
                        finish("OVER_QUERY_LIMIT", 0, errMsg);
                        renderPlacesError("Query Limit Exceeded (OVER_QUERY_LIMIT)", errMsg);
                    } else if (status === google.maps.places.PlacesServiceStatus.INVALID_REQUEST) {
                        const errMsg = "Google Places request was invalid. Check request coordinates and radius.";
                        finish("INVALID_REQUEST", 0, errMsg);
                        renderPlacesError("Invalid Request (INVALID_REQUEST)", errMsg);
                    } else if (status === google.maps.places.PlacesServiceStatus.UNKNOWN_ERROR) {
                        const errMsg = "Google Places service encountered a temporary server error. Please retry.";
                        finish("UNKNOWN_ERROR", 0, errMsg);
                        renderPlacesError("Google Places Server Error (UNKNOWN_ERROR)", errMsg);
                    } else {
                        const errMsg = `Google Places request failed: ${statusStr}`;
                        finish(statusStr, 0, errMsg);
                        renderPlacesError(`Google Places Unavailable (${statusStr})`, errMsg);
                    }
                });
                return;
            } catch (err) {
                console.warn("Browser PlacesService exception:", err);
                const errMsg = err.message || "PlacesService invocation exception";
                finish("EXCEPTION", 0, errMsg);
                renderPlacesError("PlacesService Error", errMsg);
                return;
            }
        }

        // Fallback: Check server endpoint if browser places library is not loaded
        if (!placesLibraryLoaded) {
            fetch(`/api/maps/places?query=${encodeURIComponent("hotels and restaurants near " + templeName)}&latitude=${currentLat}&longitude=${currentLng}&radius=5000`)
                .then(res => res.json())
                .then(data => {
                    if (data.results && data.results.length > 0) {
                        finish("OK", data.results.length, null);
                        renderPlacesResults(data.results);
                    } else if (data.status === "BROWSER_SEARCH_REQUIRED") {
                        const errMsg = "Google Places is not available in this browser session. The Places JavaScript library is not loaded, and the server-side Places API credential is not configured.";
                        finish("BROWSER_SEARCH_REQUIRED", 0, errMsg);
                        renderPlacesError("Google Places Unavailable", errMsg, "Ensure the Google Maps JavaScript API script is loaded with &libraries=places and that the Places API is enabled.");
                    } else if (data.status === "ZERO_RESULTS") {
                        finish("ZERO_RESULTS", 0, null);
                        renderPlacesZeroResults(`No nearby places were found within 5 km of ${escapeHtml(templeName)}.`);
                    } else {
                        const errMsg = data.message || `Google Places request failed: ${data.status}`;
                        finish(data.status || "FAILED", 0, errMsg);
                        renderPlacesError("Google Places Request Failed", errMsg);
                    }
                })
                .catch(() => {
                    const errMsg = "Google Places is not available in this browser session.";
                    finish("NETWORK_ERROR", 0, errMsg);
                    renderPlacesError("Google Places Unavailable", errMsg);
                });
        } else {
            const errMsg = "Google Places is not available in this browser session.";
            finish("NOT_AVAILABLE", 0, errMsg);
            renderPlacesError("Google Places Unavailable", errMsg);
        }
    }

    function renderPlacesResults(items) {
        if (!placesList) return;
        if (!items || items.length === 0) {
            renderPlacesZeroResults("No nearby places returned.");
            return;
        }

        let cardsHtml = "";
        items.slice(0, 10).forEach(p => {
            const rating = p.rating ? `⭐ ${p.rating} (${p.user_ratings_total || 0})` : "Rating: N/A";
            cardsHtml += `
                <div class="place-card">
                    <div class="place-title">${escapeHtml(p.name)}</div>
                    <div class="place-address">${escapeHtml(p.address || "Address unavailable")}</div>
                    <div class="place-meta">
                        <span class="place-rating">${rating}</span>
                        ${p.open_now !== null && p.open_now !== undefined ? `<span>${p.open_now ? "🟢 Open" : "🔴 Closed"}</span>` : ""}
                    </div>
                </div>
            `;
        });
        placesList.innerHTML = cardsHtml;
    }

    function renderPlacesError(title, message, hint) {
        if (!placesList) return;
        placesList.innerHTML = `
            <div class="places-error-banner">
                <div class="places-error-title">⚠️ ${escapeHtml(title)}</div>
                <div class="places-error-desc">${escapeHtml(message)}</div>
                ${hint ? `<div class="places-config-hint">💡 ${escapeHtml(hint)}</div>` : ""}
            </div>
        `;
    }

    function renderPlacesZeroResults(message) {
        if (!placesList) return;
        placesList.innerHTML = `
            <div class="places-zero-results">
                ${escapeHtml(message || "No nearby places found.")}
            </div>
        `;
    }

    function renderPlacesOffline(msg) {
        renderPlacesError("Google Places Unavailable", msg || "Google Places discovery currently offline or unconfigured. Verified temple guide remains active.");
    }

    // Sidebar temple items click listener
    if (templeList) {
        templeList.addEventListener("click", (e) => {
            const item = e.target.closest(".temple-item");
            if (!item) return;
            const tName = item.getAttribute("data-temple");
            if (!tName) return;

            document.querySelectorAll(".temple-item").forEach(i => i.classList.remove("active"));
            item.classList.add("active");

            // Pan map if loaded
            const found = templeCoordinates.find(t => t.canonical_name.toLowerCase() === tName.toLowerCase() || t.display_name.toLowerCase().includes(tName.toLowerCase()));
            if (found) {
                currentSelectedTemple = found.display_name;
                currentLat = found.latitude;
                currentLng = found.longitude;
                panToCoordinates(found.latitude, found.longitude, found.display_name);
                fetchNearbyPlaces(found.display_name, found.latitude, found.longitude);
            }
        });
    }

    // -------------------------------------------------------------
    // Native Browser Voice UI (Speech-to-Text & Text-to-Speech)
    // -------------------------------------------------------------
    let cachedVoices = [];

    function populateVoices() {
        if (!window.speechSynthesis) return;
        cachedVoices = window.speechSynthesis.getVoices();
    }

    if (window.speechSynthesis) {
        populateVoices();
        if (speechSynthesis.onvoiceschanged !== undefined) {
            speechSynthesis.onvoiceschanged = populateVoices;
        }
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition && micBtn) {
        speechRecognition = new SpeechRecognition();
        speechRecognition.continuous = false;
        speechRecognition.interimResults = false;
        speechRecognition.lang = "en-IN";

        speechRecognition.onstart = () => {
            isListening = true;
            micBtn.classList.add("listening");
        };

        speechRecognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            userQuery.value = transcript;
            isListening = false;
            micBtn.classList.remove("listening");
            chatForm.dispatchEvent(new Event("submit"));
        };

        speechRecognition.onerror = () => {
            isListening = false;
            micBtn.classList.remove("listening");
        };

        speechRecognition.onend = () => {
            isListening = false;
            micBtn.classList.remove("listening");
        };

        micBtn.addEventListener("click", () => {
            if (!speechRecognition) return;
            if (isListening) {
                speechRecognition.stop();
            } else {
                speechRecognition.lang = currentLang === "te" ? "te-IN" : (currentLang === "hi" ? "hi-IN" : "en-IN");
                speechRecognition.start();
            }
        });
    } else if (micBtn) {
        micBtn.style.display = "none";
    }

    // -------------------------------------------------------------
    // Markdown Stripping for Natural Speech Output
    // -------------------------------------------------------------
    function stripMarkdownForSpeech(text) {
        if (!text) return "";
        let clean = text;

        // 1. Remove fenced code blocks ```...```
        clean = clean.replace(/```[\s\S]*?```/g, " ");

        // 2. Remove inline code `...`
        clean = clean.replace(/`([^`]+)`/g, "$1");

        // 3. Remove UI note disclaimers e.g. *(Note: ...)* or *(Note: ... )*
        clean = clean.replace(/\*\s*\(\s*Note:[\s\S]*?\)\s*\*/gi, " ");

        // 4. Convert markdown links [Label](url) -> Label
        clean = clean.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");

        // 5. Remove citation chips e.g. [1], [2], [12]
        clean = clean.replace(/\[\d+\]/g, " ");

        // 6. Replace headers (e.g. ### Header) with Header followed by period for pause
        clean = clean.replace(/^#{1,6}\s+(.*$)/gm, "$1. ");

        // 7. Remove blockquotes (> ...)
        clean = clean.replace(/^>\s+/gm, " ");

        // 8. Replace bullet lists and numbered lists with punctuation pauses
        clean = clean.replace(/^\s*[-*+]\s+/gm, " ");
        clean = clean.replace(/^\s*\d+\.\s+/gm, " ");

        // 9. Remove bold and italic markers (* and _)
        clean = clean.replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, "$1");
        clean = clean.replace(/[*_]/g, "");

        // 10. Replace table pipes and separators
        clean = clean.replace(/\|/g, " ");

        // 11. Normalize newlines to sentence periods if missing punctuation
        clean = clean.replace(/([^\w\s.?!])\n+/g, " ");
        clean = clean.replace(/([a-zA-Z0-9])\n+/g, "$1. ");
        clean = clean.replace(/\n+/g, " ");

        // 12. Normalize multiple spaces and multiple periods
        clean = clean.replace(/\s+/g, " ");
        clean = clean.replace(/\.+/g, ".");
        clean = clean.replace(/\s+([.,?!])/g, "$1");

        return clean.trim();
    }
    window.stripMarkdownForSpeech = stripMarkdownForSpeech;

    function showVoiceNotification(message) {
        let toast = document.getElementById("voiceToast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "voiceToast";
            toast.style.cssText = "position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); background: #1e293b; color: #fbbf24; border: 1px solid #d97706; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 500; z-index: 9999; box-shadow: 0 4px 12px rgba(0,0,0,0.5); display: flex; align-items: center; gap: 8px; transition: opacity 0.3s ease;";
            document.body.appendChild(toast);
        }
        toast.innerHTML = `<span>⚠️ ${escapeHtml(message)}</span>`;
        toast.style.opacity = "1";
        toast.style.display = "flex";
        setTimeout(() => {
            toast.style.opacity = "0";
            setTimeout(() => { toast.style.display = "none"; }, 300);
        }, 4000);
    }

    function selectBestVoice(targetLang) {
        const voices = cachedVoices.length > 0 ? cachedVoices : (window.speechSynthesis ? window.speechSynthesis.getVoices() : []);
        if (!voices || voices.length === 0) return null;

        if (targetLang === "te") {
            // Target Telugu
            const teVoice = voices.find(v => v.lang.toLowerCase() === "te-in" || v.lang.toLowerCase().startsWith("te"));
            return teVoice || null;
        } else if (targetLang === "hi") {
            // Target Hindi
            const hiVoice = voices.find(v => v.lang.toLowerCase() === "hi-in" || v.lang.toLowerCase().startsWith("hi"));
            return hiVoice || null;
        } else {
            // Target English: en-IN -> en-US -> en-GB -> system default
            const enIn = voices.find(v => v.lang.toLowerCase() === "en-in");
            if (enIn) return enIn;
            const enUs = voices.find(v => v.lang.toLowerCase() === "en-us");
            if (enUs) return enUs;
            const enGb = voices.find(v => v.lang.toLowerCase() === "en-gb");
            if (enGb) return enGb;
            const anyEn = voices.find(v => v.lang.toLowerCase().startsWith("en"));
            if (anyEn) return anyEn;
            return voices[0] || null;
        }
    }

    // -------------------------------------------------------------
    // Browser-Native Text-to-Speech Playback Controls (Play / Pause / Resume / Stop)
    // -------------------------------------------------------------
    const SPEECH_ICONS = {
        play: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>',
        pause: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>',
        resume: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>',
        stop: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect></svg>'
    };

    let activeSpeechState = "idle"; // "idle" | "playing" | "paused"
    let activeUtterance = null;
    let activeSpeechContainer = null;
    let speechKeepAliveTimer = null;

    function renderSpeechControlsHtml(state) {
        if (state === "playing") {
            return `
                <button class="btn-speech-control btn-speech-pause" title="Pause speech" onclick="handleSpeechAction(this, 'pause')">
                    ${SPEECH_ICONS.pause}
                    <span class="btn-speech-label">Pause</span>
                </button>
                <button class="btn-speech-control btn-speech-stop" title="Stop speech" onclick="handleSpeechAction(this, 'stop')">
                    ${SPEECH_ICONS.stop}
                    <span class="btn-speech-label">Stop</span>
                </button>
            `;
        } else if (state === "paused") {
            return `
                <button class="btn-speech-control btn-speech-resume" title="Resume speech" onclick="handleSpeechAction(this, 'resume')">
                    ${SPEECH_ICONS.resume}
                    <span class="btn-speech-label">Resume</span>
                </button>
                <button class="btn-speech-control btn-speech-stop" title="Stop speech" onclick="handleSpeechAction(this, 'stop')">
                    ${SPEECH_ICONS.stop}
                    <span class="btn-speech-label">Stop</span>
                </button>
            `;
        } else {
            // idle
            return `
                <button class="btn-speech-control btn-speech-play" title="Read Aloud" onclick="handleSpeechAction(this, 'play')">
                    ${SPEECH_ICONS.play}
                    <span class="btn-speech-label">Read</span>
                </button>
            `;
        }
    }

    function updateSpeechControlsUi(container, state) {
        if (!container) return;
        container.setAttribute("data-speech-state", state);
        container.innerHTML = renderSpeechControlsHtml(state);
    }

    function resetActiveSpeechUi() {
        clearSpeechKeepAlive();
        if (activeSpeechContainer) {
            updateSpeechControlsUi(activeSpeechContainer, "idle");
            activeSpeechContainer = null;
        }
        activeSpeechState = "idle";
        activeUtterance = null;
    }

    function startSpeechKeepAlive() {
        clearSpeechKeepAlive();
        // Periodically pulse pause/resume while playing to prevent Chromium 15s engine timeout during long speech
        speechKeepAliveTimer = setInterval(() => {
            if (!window.speechSynthesis) return;
            if (activeSpeechState === "playing" && window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
                window.speechSynthesis.pause();
                window.speechSynthesis.resume();
            }
        }, 10000);
    }

    function clearSpeechKeepAlive() {
        if (speechKeepAliveTimer) {
            clearInterval(speechKeepAliveTimer);
            speechKeepAliveTimer = null;
        }
    }

    window.handleSpeechAction = function(btn, action) {
        if (!window.speechSynthesis) {
            showVoiceNotification("Speech synthesis is not supported in this browser.");
            return;
        }

        const container = btn.closest(".speech-controls") || btn.parentElement;
        if (!container) return;

        if (action === "pause") {
            if (activeSpeechState === "playing") {
                window.speechSynthesis.pause();
                activeSpeechState = "paused";
                clearSpeechKeepAlive();
                updateSpeechControlsUi(container, "paused");
            }
            return;
        }

        if (action === "resume") {
            if (activeSpeechState === "paused" && activeUtterance) {
                window.speechSynthesis.resume();
                activeSpeechState = "playing";
                startSpeechKeepAlive();
                updateSpeechControlsUi(container, "playing");
            }
            return;
        }

        if (action === "stop") {
            window.speechSynthesis.cancel();
            resetActiveSpeechUi();
            return;
        }

        if (action === "play") {
            // If already speaking this message, ignore duplicate rapid clicks
            if (activeSpeechContainer === container && activeSpeechState === "playing") {
                return;
            }

            // Cancel any previous speech
            window.speechSynthesis.cancel();
            resetActiveSpeechUi();

            const bubble = btn.closest(".msg-bubble-wrapper").querySelector(".msg-bubble");
            if (!bubble) return;

            const rawText = bubble.getAttribute("data-raw-answer") || bubble.innerText;
            const cleanText = stripMarkdownForSpeech(rawText);
            if (!cleanText) return;

            // Determine language from content script or current selection
            let targetLang = "en";
            if (/[\u0C00-\u0C7F]/.test(cleanText)) {
                targetLang = "te";
            } else if (/[\u0900-\u097F]/.test(cleanText)) {
                targetLang = "hi";
            } else if (currentLang === "te" || currentLang === "hi") {
                targetLang = currentLang;
            }

            const voice = selectBestVoice(targetLang);

            // Regional voice fallback handling
            if (targetLang === "te" && !voice) {
                showVoiceNotification("Telugu voice is not available in this browser.");
                return;
            }

            const utterance = new SpeechSynthesisUtterance(cleanText);
            if (voice) {
                utterance.voice = voice;
                utterance.lang = voice.lang;
            } else {
                utterance.lang = targetLang === "hi" ? "hi-IN" : "en-IN";
            }
            utterance.rate = 1.0;

            utterance.onstart = () => {
                activeSpeechState = "playing";
                updateSpeechControlsUi(container, "playing");
                startSpeechKeepAlive();
            };

            utterance.onpause = () => {
                if (activeSpeechState !== "paused") {
                    activeSpeechState = "paused";
                    clearSpeechKeepAlive();
                    updateSpeechControlsUi(container, "paused");
                }
            };

            utterance.onresume = () => {
                if (activeSpeechState !== "playing") {
                    activeSpeechState = "playing";
                    startSpeechKeepAlive();
                    updateSpeechControlsUi(container, "playing");
                }
            };

            utterance.onend = () => {
                if (activeUtterance === utterance) {
                    resetActiveSpeechUi();
                }
            };

            utterance.onerror = (e) => {
                if (activeUtterance === utterance) {
                    resetActiveSpeechUi();
                }
            };

            activeUtterance = utterance;
            activeSpeechContainer = container;
            activeSpeechState = "playing";
            updateSpeechControlsUi(container, "playing");

            if (window.speechSynthesis.paused) {
                window.speechSynthesis.resume();
            }
            window.speechSynthesis.speak(utterance);
        }
    };

    window.playSpeechText = function(btn) {
        window.handleSpeechAction(btn, "play");
    };

    // -------------------------------------------------------------
    // Voice Diagnostics (Safe & Credential-Free)
    // -------------------------------------------------------------
    window.getVoiceDiagnostics = function(lang = "en") {
        const supported = !!window.speechSynthesis;
        const voices = supported ? (cachedVoices.length > 0 ? cachedVoices : window.speechSynthesis.getVoices()) : [];
        const matched = selectBestVoice(lang);

        return {
            speechSynthesisSupported: supported,
            availableVoicesCount: voices.length,
            selectedVoice: matched ? matched.name : (voices.length > 0 ? "System Default" : "None"),
            selectedLanguage: lang
        };
    };

    // -------------------------------------------------------------
    // Utility Helpers
    // -------------------------------------------------------------
    function scrollToBottom() {
        messageArea.scrollTop = messageArea.scrollHeight;
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    function formatMarkdownText(md) {
        if (!md) return "";
        let html = escapeHtml(md);

        // Unescape escaped hashes like \#### or \###
        html = html.replace(/\\(#+)/g, "$1");

        // Bold
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        // Italic
        html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");
        // Headers
        html = html.replace(/^#### (.*$)/gim, "<h4>$1</h4>");
        html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
        html = html.replace(/^## (.*$)/gim, "<h2>$1</h2>");
        html = html.replace(/^# (.*$)/gim, "<h1>$1</h1>");
        // Blockquotes
        html = html.replace(/^> (.*$)/gim, "<blockquote>$1</blockquote>");
        // Bullet lists
        html = html.replace(/^\- (.*$)/gim, "<li>$1</li>");
        // Wrap adjacent li elements into ul
        html = html.replace(/(<li>.*?<\/li>)/gs, "<ul>$1</ul>");
        html = html.replace(/<\/ul>\s*<ul>/g, "");
        // Newlines to line breaks (outside lists)
        html = html.replace(/\n\n/g, "<br><br>");
        html = html.replace(/\n/g, "<br>");

        return html;
    }

    // -------------------------------------------------------------
    // Full Page Authentication State & View Controller
    // -------------------------------------------------------------
    const authPage = document.getElementById("authPage");
    const appLayout = document.getElementById("appLayout");
    const headerUserName = document.getElementById("headerUserName");
    const logoutBtn = document.getElementById("logoutBtn");

    // Views
    const viewLogin = document.getElementById("viewLogin");
    const viewRegister = document.getElementById("viewRegister");
    const viewForgotPassword = document.getElementById("viewForgotPassword");
    const viewResetPassword = document.getElementById("viewResetPassword");

    // Navigation Switch Links
    const linkToRegister = document.getElementById("linkToRegister");
    const linkToLoginFromReg = document.getElementById("linkToLoginFromReg");
    const linkToForgotPassword = document.getElementById("linkToForgotPassword");
    const linkToLoginFromForgot = document.getElementById("linkToLoginFromForgot");
    const linkToLoginFromReset = document.getElementById("linkToLoginFromReset");

    // Forms
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const forgotPasswordForm = document.getElementById("forgotPasswordForm");
    const resetPasswordForm = document.getElementById("resetPasswordForm");

    // Message Elements
    const loginError = document.getElementById("loginError");
    const registerError = document.getElementById("registerError");
    const registerSuccess = document.getElementById("registerSuccess");
    const forgotError = document.getElementById("forgotError");
    const forgotSuccess = document.getElementById("forgotSuccess");
    const resetError = document.getElementById("resetError");
    const resetSuccess = document.getElementById("resetSuccess");
    const resetTokenValue = document.getElementById("resetTokenValue");

    function clearAuthMessages() {
        if (loginError) loginError.style.display = "none";
        if (registerError) registerError.style.display = "none";
        if (registerSuccess) registerSuccess.style.display = "none";
        if (forgotError) forgotError.style.display = "none";
        if (forgotSuccess) forgotSuccess.style.display = "none";
        if (resetError) resetError.style.display = "none";
        if (resetSuccess) resetSuccess.style.display = "none";
    }

    function switchAuthView(viewName) {
        clearAuthMessages();
        if (viewName === "AUTHENTICATED_APP") {
            if (authPage) authPage.style.display = "none";
            if (appLayout) appLayout.style.display = "flex";
            if (window.lucide) lucide.createIcons();
            if (googleMap) google.maps.event.trigger(googleMap, "resize");
            return;
        }

        // Show Auth Page, hide main application
        if (authPage) authPage.style.display = "flex";
        if (appLayout) appLayout.style.display = "none";

        if (viewLogin) viewLogin.style.display = (viewName === "AUTH_LOGIN") ? "block" : "none";
        if (viewRegister) viewRegister.style.display = (viewName === "AUTH_REGISTER") ? "block" : "none";
        if (viewForgotPassword) viewForgotPassword.style.display = (viewName === "AUTH_FORGOT_PASSWORD") ? "block" : "none";
        if (viewResetPassword) viewResetPassword.style.display = (viewName === "AUTH_RESET_PASSWORD") ? "block" : "none";

        if (window.lucide) lucide.createIcons();
    }

    // Link Click Event Listeners
    if (linkToRegister) {
        linkToRegister.addEventListener("click", () => switchAuthView("AUTH_REGISTER"));
    }
    if (linkToLoginFromReg) {
        linkToLoginFromReg.addEventListener("click", () => switchAuthView("AUTH_LOGIN"));
    }
    if (linkToForgotPassword) {
        linkToForgotPassword.addEventListener("click", () => switchAuthView("AUTH_FORGOT_PASSWORD"));
    }
    if (linkToLoginFromForgot) {
        linkToLoginFromForgot.addEventListener("click", () => switchAuthView("AUTH_LOGIN"));
    }
    if (linkToLoginFromReset) {
        linkToLoginFromReset.addEventListener("click", () => {
            // Remove reset_token query parameter from address bar
            window.history.replaceState({}, document.title, window.location.pathname);
            switchAuthView("AUTH_LOGIN");
        });
    }

    // 1. Login Form Submit
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            clearAuthMessages();
            const email = document.getElementById("loginEmail").value.trim();
            const password = document.getElementById("loginPassword").value;

            try {
                const res = await fetch("/api/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password })
                });
                const data = await res.json();
                if (!res.ok) {
                    if (loginError) {
                        loginError.textContent = data.detail || "Invalid email or password.";
                        loginError.style.display = "block";
                    }
                    return;
                }
                localStorage.setItem("pilgrim_jwt", data.access_token);
                if (headerUserName) {
                    headerUserName.textContent = data.user ? (data.user.name || data.user.email) : "Pilgrim";
                }
                switchAuthView("AUTHENTICATED_APP");
            } catch (err) {
                if (loginError) {
                    loginError.textContent = "Unable to connect to server. Please try again.";
                    loginError.style.display = "block";
                }
            }
        });
    }

    // 2. Register Form Submit
    if (registerForm) {
        registerForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            clearAuthMessages();
            const name = document.getElementById("regName").value.trim();
            const email = document.getElementById("regEmail").value.trim();
            const password = document.getElementById("regPassword").value;
            const confirmPassword = document.getElementById("regPasswordConfirm").value;

            if (password !== confirmPassword) {
                if (registerError) {
                    registerError.textContent = "Passwords do not match.";
                    registerError.style.display = "block";
                }
                return;
            }

            try {
                const res = await fetch("/api/auth/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, email, password })
                });
                const data = await res.json();
                if (!res.ok) {
                    if (registerError) {
                        registerError.textContent = data.detail || "Registration failed.";
                        registerError.style.display = "block";
                    }
                    return;
                }
                if (registerSuccess) {
                    registerSuccess.textContent = "Registration successful! A verification email has been sent. Redirecting to login...";
                    registerSuccess.style.display = "block";
                }
                setTimeout(() => {
                    switchAuthView("AUTH_LOGIN");
                    const loginEmailInput = document.getElementById("loginEmail");
                    if (loginEmailInput) loginEmailInput.value = email;
                }, 2000);
            } catch (err) {
                if (registerError) {
                    registerError.textContent = "Unable to connect to server. Please try again.";
                    registerError.style.display = "block";
                }
            }
        });
    }

    // 3. Forgot Password Form Submit
    if (forgotPasswordForm) {
        forgotPasswordForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            clearAuthMessages();
            const email = document.getElementById("forgotEmail").value.trim();

            try {
                const res = await fetch("/api/auth/forgot-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email })
                });
                const data = await res.json();
                if (forgotSuccess) {
                    forgotSuccess.textContent = data.message || "If an account exists for this email, a password reset link has been sent.";
                    forgotSuccess.style.display = "block";
                }
            } catch (err) {
                if (forgotError) {
                    forgotError.textContent = "Unable to connect to server. Please try again.";
                    forgotError.style.display = "block";
                }
            }
        });
    }

    // 4. Reset Password Form Submit
    if (resetPasswordForm) {
        resetPasswordForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            clearAuthMessages();
            const token = resetTokenValue ? resetTokenValue.value : "";
            const new_password = document.getElementById("resetPasswordInput").value;
            const confirm_password = document.getElementById("resetPasswordConfirmInput").value;

            if (new_password !== confirm_password) {
                if (resetError) {
                    resetError.textContent = "New passwords do not match.";
                    resetError.style.display = "block";
                }
                return;
            }

            try {
                const res = await fetch("/api/auth/reset-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ token, new_password })
                });
                const data = await res.json();
                if (!res.ok) {
                    if (resetError) {
                        resetError.textContent = data.detail || "Failed to reset password.";
                        resetError.style.display = "block";
                    }
                    return;
                }
                if (resetSuccess) {
                    resetSuccess.textContent = "Password reset successfully! Redirecting to sign in...";
                    resetSuccess.style.display = "block";
                }
                setTimeout(() => {
                    window.history.replaceState({}, document.title, window.location.pathname);
                    switchAuthView("AUTH_LOGIN");
                }, 2000);
            } catch (err) {
                if (resetError) {
                    resetError.textContent = "Unable to connect to server. Please try again.";
                    resetError.style.display = "block";
                }
            }
        });
    }

    // 5. Logout
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            localStorage.removeItem("pilgrim_jwt");
            createFreshSession();
            switchAuthView("AUTH_LOGIN");
        });
    }

    // 6. Startup Authentication / URL Token Check
    async function initAuthFlow() {
        // Check for URL query parameter ?reset_token=...
        const urlParams = new URLSearchParams(window.location.search);
        const resetToken = urlParams.get("reset_token");
        if (resetToken) {
            if (resetTokenValue) resetTokenValue.value = resetToken;
            switchAuthView("AUTH_RESET_PASSWORD");
            return;
        }

        const token = localStorage.getItem("pilgrim_jwt");
        if (!token) {
            switchAuthView("AUTH_LOGIN");
            return;
        }

        try {
            const res = await fetch("/api/auth/me", {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (res.ok) {
                const user = await res.json();
                if (headerUserName) {
                    headerUserName.textContent = user.name || user.email;
                }
                switchAuthView("AUTHENTICATED_APP");
            } else {
                localStorage.removeItem("pilgrim_jwt");
                switchAuthView("AUTH_LOGIN");
            }
        } catch (e) {
            console.warn("Auth startup verification error:", e);
            switchAuthView("AUTH_LOGIN");
        }
    }

    // Run startup authentication check
    initAuthFlow();

    // Initialize Maps
    initGoogleMaps();
});


