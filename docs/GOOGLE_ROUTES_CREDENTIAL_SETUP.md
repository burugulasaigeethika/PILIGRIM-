# Google Cloud Dual-Credential Architecture: Browser (Maps/Places) vs Server (Routes)

This document details the security architecture and exact configuration requirements in Google Cloud Console for operating PilgrimAI with strict credential isolation.

---

## 1. Architecture Overview & Credential Separation

PilgrimAI operates across two distinct execution environments that must NEVER share credential configurations:

| Credential | Variable | Execution Context | Application Restriction | API Restriction |
| :--- | :--- | :--- | :--- | :--- |
| **Browser Credential** | `GOOGLE_MAPS_API_KEY` | Client Web Browser | **Websites / HTTP referrers** (`http://localhost:8000/*`, `http://127.0.0.1:8000/*`) | Maps JavaScript API, Places API |
| **Server Credential** | `GOOGLE_ROUTES_API_KEY` | FastAPI Backend (`NavigationAdapter`) | **IP addresses** (Server Egress IP) | Routes API only |

---

## 2. Existing Browser Credential (PRESERVED)

The existing browser credential remains completely unchanged:

```text
Variable:
GOOGLE_MAPS_API_KEY

Application restriction:
Website / HTTP referrer

Allowed origins:
http://localhost:8000/*
http://127.0.0.1:8000/*

API restrictions:
Maps JavaScript API
Places API

Purpose:
Maps JavaScript SDK rendering & Places library in the client browser
```

The browser receives this key at runtime strictly via `GET /api/maps/config`. It is never hardcoded in source code or Git.

---

## 3. Dedicated Server Routes Credential

```text
Variable:
GOOGLE_ROUTES_API_KEY

Application restriction:
IP addresses (Egress IP of server hosting FastAPI)

API restriction:
Routes API only

Purpose:
FastAPI backend route computations via LiveNavigationAgent / NavigationAdapter
```

> [!WARNING]
> **DO NOT make the server Routes key unrestricted merely to bypass HTTP 403.**  
> API restrictions must be strictly limited to **Routes API**.

---

## 4. Crucial Network Distinction: Localhost vs Public Server IP

### Why `127.0.0.1` Cannot Be Used in Google Cloud Console:
- `localhost` (`127.0.0.1`) is a loopback address internal to your local computer.
- When Python sends a server-side HTTP request to Google Routes API (`https://routes.googleapis.com`), Google servers see your **public egress IP address** (assigned by your ISP or cloud gateway), **NOT** `127.0.0.1`.
- Entering `127.0.0.1` in the Google Cloud Console IP restriction will cause Google to reject every request with `HTTP 403 Forbidden`.

### Deployment & Local Development Environments:

1. **Production / Staging Server (Recommended Production Setup)**:
   - Identify your server's static outbound (egress) public IPv4 or IPv6 address.
   - In Google Cloud Console, select **Application restriction > IP addresses** and enter the static server IP.
   - Only requests originating from that specific server IP will be authorized by Google.

2. **Local Development Practicalities**:
   - On residential internet connections, your public IP is dynamically assigned by your ISP and changes periodically.
   - If using IP restrictions locally: find your current public IP via `curl https://api.ipify.org` and add it to the allowed IP list in Google Cloud Console.
   - Note: Whenever your router reconnects or your ISP reassigns your IP, the Google Cloud Console IP list must be updated accordingly.

---

## 5. Google Cloud Console Step-by-Step Setup

1. **Log in to Google Cloud Console**:
   Go to **APIs & Services > Credentials** in your Google Cloud project.

2. **Create the Server Key**:
   - Click **+ CREATE CREDENTIALS > API key**.
   - Name the key: `PilgrimAI Server Routes Key`.

3. **Configure API Restrictions (Mandatory)**:
   - Under **API restrictions**, choose **Restrict key**.
   - Select **Routes API**. Ensure no other APIs are selected.

4. **Configure Application Restrictions**:
   - Under **Application restrictions**, select **IP addresses**.
   - Enter your server's static egress public IP address (or current development public IP).
   - Click **Save**. Note: Google Cloud restriction changes may take 1 to 5 minutes to propagate globally.

---

## 6. Local Environment Configuration

Add the server credential to your local `.env` file (which is git-ignored):

```bash
# In .env (DO NOT COMMIT)
GOOGLE_MAPS_API_KEY=<browser_website_restricted_key>
GOOGLE_ROUTES_API_KEY=<server_ip_restricted_key>
```

---

## 7. Verification

Once configured in `.env`, verify live route resolution by executing:

```bash
python scratch/test_frontend_queries.py
```

Expected result:
```text
[PASS] Navigation -> Agent: live_navigation (or response_aggregator) | Distance, Duration, and Route Details retrieved.
```
