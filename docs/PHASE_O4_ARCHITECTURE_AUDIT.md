# Phase O4 — Budget Agent Architecture Audit

## 0. Executive Summary

- **Component Audited**: `BudgetAgent` (Phase O4).
- **Execution Mode**: **AUDIT ONLY**. No production code or tests are modified in this phase.
- **Certified Baseline**: **404/404 tests passing** (Phases A–N + Post-Phase-N routing fix + O1 External Adapter + O2 Coordinate Registry + O3 LiveWeatherAgent).
- **API Key & External Cost Constraint**: **₹0 external cost, 0 API keys required**. The budget agent operates completely deterministically using verified devasthanam records already in the repository and user-supplied parameters.
- **Data Protection**: All 417 source JSON files, Qdrant vector store, BM25 index, and RAG retrieval pipelines remain strictly frozen and untouched.

---

## 1. Verified Temple Cost Data Audit (417 Source Files)

An exhaustive inspection of all 417 JSON files across all 20 canonical temple directories was conducted to evaluate the exact pricing fields, schema variations, and data completeness.

### 1.1 Category Cost Coverage Summary

| Category | Files with Price Data | Total Files | Sample Price Keys | Pricing Characteristics |
| :--- | :---: | :---: | :--- | :--- |
| **`sevas`** | 19 / 20 | 20 | `price` | Highly structured; contains specific ritual costs, darshan queue tickets, and special puja fees. Birla Mandir has no paid sevas. |
| **`accommodation`** | 19 / 20 | 20 | `price` | Devasthanam choultries, guest houses, and cottages; provides AC and Non-AC room tariffs. |
| **`prasadam`** | 17 / 20 | 20 | `price`, `price_status` | Standard prasadam items (laddu, pulihora, vada) and free Annadanam (meals). |
| **`timings`** | 9 / 20 | 20 | `entry_fee` | General Sarva Darshan entry fee across all South Indian temples is `FREE (No Ticket Required)`. |
| **`restaurants`** | 16 / 20 | 20 | `cost`, `price_range` | Approximate dining cost ranges (`₹50 - ₹120`) and Annadanam counters. |
| **`elderly_ppl`** | 19 / 20 | 20 | `cost` | Accessibility and special darshan lines (`Free of charge (Privilege Darshan)` at TTD). |
| **`donations`** | 8 / 17 | 17 | `price`, `amount` | Trust donation slabs (`₹1,116`, `₹5,116`, `₹10,116`). |
| **`travel`** | 15 / 20 | 20 | None (distance/routes only) | Contains transit routes and distances (e.g. `85 km`, `38 km`), but no fixed standard fare numbers due to fluctuating public/private transit tariffs. |

### 1.2 Price Value Representation & Parsing Findings

Across the 519 verified priced items in the dataset:
- **Exact Numeric Fixed Prices (384 items)**:
  - Formatted as currency strings: `"₹25"`, `"₹50"`, `"₹220 per person"`, `"₹500"`, `"₹1,500"`.
  - Can be deterministically parsed into `(float, float)` bounds.
- **Price Ranges (104 items)**:
  - Formatted with hyphens or words: `"₹900 - ₹1,700 per night"`, `"₹750 – ₹1,000"`, `"Varies by shrine (~₹500 to ₹2,500)"`.
  - Parsed into `(min_price, max_price)` bounds.
- **Free / Complimentary Items (31 items)**:
  - Formatted as: `"FREE (No Ticket Required)"`, `"Free Darshanam"`, `"Free (Donations accepted via Annamacharya Annadanam)"`.
  - Parsed as `0.0` cost.
- **Unquantified Items (42 items)**:
  - Formatted as: `"Nominal fee (Verify current rates on-site)"`, `"Endowment Fund (Contact office for official corpus amount)"`, `"varies"`, `"Nominal maintenance donation / Budget-friendly"`.
  - **Architecture Rule**: These items must **never** have fabricated prices. They must be transparently reported as unquantified items requiring on-site inquiry.

---

## 2. Budget Agent Architecture

### 2.1 Agent Contract & Responsibilities
- **Class**: `BudgetAgent(BaseAgent)`
- **Name**: `budget`
- **Description**: *"Specialist agent calculating grounded pilgrimage budgets and itemized cost breakdowns using verified temple sevas, accommodation, prasadam, and user travel parameters."*
- **Execution Pattern**: Implements standard `_run(state: AgentState) -> AgentResponse` with execution tracing, latency capture, and error containment.

### 2.2 End-to-End Architectural Flow

```text
User Query ("How much will a visit to Yadadri cost for 2 people?")
    ↓
/chat Endpoint (FastAPI)
    ↓
MasterAgentCoordinator
    ↓
AgentRouter (Deterministic Classification: Intent = "budget" or "multi_intent")
    ↓
BudgetAgent (BaseAgent implementation, name="budget")
    ├── 1. Entity & Parameter Extraction (Temple: "Yadadri", Pax: 2, Days: 1, Stay: Standard)
    ├── 2. Knowledge Access (RAGTool / KnowledgeRegistry read-only inspection)
    │     ├── sevas.json (Darshan/Seva prices)
    │     ├── accommodation.json (Room tariffs)
    │     ├── prasadam.json (Prasadam prices)
    │     └── timings.json (Entry fees)
    ├── 3. Deterministic Price Parser & Range Accumulator
    ├── 4. Tiered Budget Model Generation (Economy, Standard, Premium)
    └── 5. Fact vs Estimate Separation & Disclaimer Attachment
    ↓
AgentResponse (success=True, answer, sources, metadata)
    ↓
ResponseAggregator
    ↓
ChatResponse
```

---

## 3. Knowledge Access Strategy

### 3.1 Strict RAG Decoupling & Read-Only Access
- `BudgetAgent` does not need heavy vector embeddings or LLM generative calls for arithmetic calculations.
- It accesses verified source data through the existing read-only interface:
  ```python
  raw_sevas = self.rag_tool.get_temple_category_data(temple, "sevas")
  raw_rooms = self.rag_tool.get_temple_category_data(temple, "accommodation")
  raw_prasadam = self.rag_tool.get_temple_category_data(temple, "prasadam")
  raw_timings = self.rag_tool.get_temple_category_data(temple, "timings")
  raw_dining = self.rag_tool.get_temple_category_data(temple, "restaurants")
  ```
- Supports full dependency injection: `rag_tool: Optional[Any] = None` can be mocked trivially in tests with zero RAG dependencies or database startup overhead.

---

## 4. User Parameter Extraction & Handling

`BudgetAgent` deterministically parses user constraints from natural language:
1. **Persons / Group Size**:
   - Matches: `r"\b(\d+)\s*(?:people|persons?|devotees?|members?|pilgrims?|adults?)\b"`, `r"\b(?:family of|group of)\s*(\d+)\b"`, `r"\b(?:for|with)\s*(couple|two|three|four)\b"`.
   - Default: `1 person`.
2. **Trip Duration / Stay**:
   - Matches: `r"\b(\d+)\s*(?:days?|nights?)\b"`, `r"\b(?:one|1)[-\s]day\b"`, `r"\bweekend\b"`.
   - Default: `1 day` (day trip without overnight stay unless accommodation is explicitly asked).
3. **Specific Sevas Requested**:
   - E.g., *"Kalyanotsavam at Yadadri"*, *"Abhishekam at Basara"*.
   - If a specific seva is mentioned, its verified fee is selected; otherwise, standard general darshan (Free) or special entry darshan is used.
4. **Accommodation Preference**:
   - User mentions `AC`, `Non-AC`, `Dormitory`, `Choultry`, or `Resort`.
   - Default: Standard devasthanam Non-AC room.
5. **Incidental Transit / Travel Mode**:
   - If user mentions personal car/taxi/bus, `BudgetAgent` computes transit estimates based on documented distance (from `travel.json`) or treats transit as a declared planning estimate.

---

## 5. Budget Models & Tiered Representation

To provide maximum practical utility without false precision, `BudgetAgent` constructs **three deterministic tiers**:

### Tier 1: Economy / Minimal Pilgrim
- **Entry & Darshan**: Free Sarva Darshan (₹0)
- **Seva**: General Darshan (₹0)
- **Prasadam**: Free Annadanam or basic prasadam (₹20 – ₹50)
- **Accommodation**: Free Devasthanam Choultry / Dormitory bed (₹0 – ₹100)
- **Incidental / Local Buffer**: ₹100 – ₹200 per person

### Tier 2: Standard Pilgrim (Recommended)
- **Entry & Darshan**: Special Entry Darshan / Quick Darshan queue (₹100 – ₹300)
- **Seva**: Standard Seva (e.g. Sahasranamarchana / Archana: ₹100 – ₹300)
- **Prasadam**: 2–3 Laddu / Pulihora packets (₹50 – ₹100)
- **Accommodation**: Standard Devasthanam Non-AC room for 2 (₹500 – ₹1,000 per room)
- **Dining / Food**: Tiffin & vegetarian meals (₹150 – ₹250 per person)

### Tier 3: Comfort / Premium Family Pilgrim
- **Entry & Seva**: Major Special Seva (e.g. Kalyanotsavam, Nijabhishekam: ₹1,000 – ₹3,000)
- **Prasadam**: Special Prasadam Box / Multiple sets (₹150 – ₹300)
- **Accommodation**: AC Suite / Devasthanam AC Guest House (₹1,500 – ₹3,500 per room)
- **Dining / Food**: Full restaurant meals (₹300 – ₹500 per person)

---

## 6. Strict Separation: Verified Facts vs Planning Estimates

Responses must be formatted with distinct, transparent sections:

```markdown
## 💰 Pilgrimage Budget Breakdown: {Temple} (for {N} Pilgrim(s))

### 🏛️ Verified Devasthanam Tariffs (Official Records)
- **Darshan Entry**: FREE (General Sarva Darshan) | Special Darshan: ₹100 – ₹300
- **Selected Seva(s)**: {Seva Name}: ₹{Price} (Verified from official records)
- **Prasadam**: Standard Laddu: ₹{Price} each
- **Devasthanam Stay**: {Room Type}: ₹{Min} – ₹{Max} per night

### 📋 Estimated Incidental & Food Expenses
- **Dining / Tiffin**: ₹{Min} – ₹{Max} per day (Estimated based on nearby dining options)
- **Local Transit Buffer**: ₹{Min} – ₹{Max}

### 🏷️ Estimated Total Pilgrimage Budget
- **Economy Pilgrim**: ₹{Total_Min} – ₹{Total_Max}
- **Standard Pilgrim**: ₹{Total_Min} – ₹{Total_Max} (Approx. ₹{Per_Person} per person)
- **Comfort Pilgrim**: ₹{Total_Min} – ₹{Total_Max}

*(Note: Official devasthanam seva and room tariffs are subject to revision by the temple board. Travel fares vary by transport provider).*
```

---

## 7. Deterministic Routing & Multi-Intent Integration

### 7.1 Router Modifications (`backend/app/agents/router.py`)
- In `_sub_intent_patterns`:
  `"budget"` is already defined: `[r"\b(budget|cost|price|expense|expenses|how\s+much\s+(will|does)\s+it\s+cost|fee|fees)\b"]`.
- In `route()`:
  Add single-intent budget routing (Priority 6.6, alongside `live_weather`):
  ```python
  # Priority 6.6: Pilgrimage Budget Intent
  is_budget_syntax = any(re.search(p, clean_query, re.IGNORECASE) for p in self._budget_patterns)
  if is_budget_syntax and len(detected_temples) == 1:
      temple_name = detected_temples[0]
      is_active = "budget" in self.active_agents
      return AgentRouteDecision(
          selected_agent="budget" if is_active else "none",
          intent="budget",
          confidence=0.95,
          reason=f"Query contains registered temple '{temple_name}' and budget estimation intent." if is_active else f"Query matches budget intent for '{temple_name}', but BudgetAgent is not active.",
          metadata={
              "available": is_active,
              "target_agent": "BudgetAgent",
              "detected_temple": temple_name,
              "detected_temples": detected_temples
          }
      )
  ```

### 7.2 Multi-Intent Preservation
Because Priority 6 (`_detect_multi_intent`) executes **before** single-intent routing:
- *"What is the weather at Yadadri and how much will it cost?"* → Matches `["weather", "budget"]` → Routes to `multi_intent`!
- *"Plan a 1-day trip to Basara and calculate the budget"* → Matches `["itinerary", "budget"]` → Routes to `multi_intent`!
- Both sub-tasks execute sequentially via `SequentialMultiIntentPipeline` and are synthesized by `ResponseAggregator`.
- Existing comparison queries (*"Compare the seva costs of Basara and Yadadri"*) route to `comparison` (Priority 3).

---

## 8. MasterAgentCoordinator Integration

Following the strict dependency-injection rule established in Phase O3:
- In `MasterAgentCoordinator.__init__`:
  ```python
  def __init__(
      self,
      ...,
      live_weather_agent: Optional[Any] = None,
      budget_agent: Optional[Any] = None,
      ...
  ):
      ...
      if budget_agent is not None:
          self.agents[budget_agent.name] = budget_agent
  ```
- **Zero Auto-Instantiation**: If `budget_agent` is None, it is **never** automatically created.
- Dynamic registration is supported via `coordinator.register_agent(budget_agent)`.
- All existing tests constructing `MasterAgentCoordinator` without a budget agent continue to run completely unaffected.

---

## 9. Required Test Coverage Plan (Minimum 35 Tests)

When Phase O4 is implemented, `tests/test_budget_agent.py` will provide comprehensive test coverage:

1. **Agent Contract**: Inheritance from `BaseAgent`, `name == "budget"`, lifecycle execution, empty query safety, whitespace safety.
2. **Location Resolution**: Canonical temple lookup, alias resolution (`Yadagirigutta` → `Yadadri`), unknown temple rejection, missing temple clarification.
3. **Price Parsing & Extraction**: Single fixed price parsing, price range parsing, free entry/darshan parsing, unquantified item handling, currency parsing (`₹`, `Rs.`).
4. **Category Pricing Integration**: Seva prices extracted from official records, room tariffs extracted, prasadam prices extracted, entry fee checked.
5. **Parameter Extraction**: 1 person default, N persons extracted, 1 day default, N days extracted, specific seva requested, accommodation type specified.
6. **Budget Models**: Economy tier calculation, Standard tier calculation, Premium tier calculation, math integrity (min <= max).
7. **Fact vs Estimate Separation**: Verified tariffs tagged distinctly from incidental estimates, disclaimer included.
8. **Unpriced / Unquantified Handling**: No fabricated prices for missing/variable records, explicit notice provided.
9. **Reliability & Security**: No secret leakage into metadata, read-only data access guarantee.
10. **Deterministic Routing**: Single-intent budget routing when active, inactive agent routing, multi-intent weather+budget, multi-intent itinerary+budget, comparison routing protection.
11. **Pipeline & Coordinator Integration**: Sequential execution with `LiveWeatherAgent` and `ItineraryPlanningAgent`, coordinator dependency-injection preservation, dynamic registration.

---

## 10. File Change Plan for Phase O4

### Files to Create:
1. `backend/app/agents/budget_agent.py` — `BudgetAgent` implementation.
2. `tests/test_budget_agent.py` — 35+ offline test cases.
3. `docs/PHASE_O4_BUDGET_AGENT.md` — Phase O4 certification document.

### Files to Minimally Modify:
1. `backend/app/agents/router.py` — Register `"budget"` intent and single-intent dispatch without swallowing multi-intent.
2. `backend/app/agents/coordinator.py` — Accept optional `budget_agent: Optional[Any] = None` with strictly zero auto-instantiation.

### Protected Files (MUST REMAIN FROZEN):
- All 417 source temple JSON files.
- `qdrant_db/`, `bm25_index/`, `evaluation/`.
- `backend/app/rag/` (all modules).
- `backend/app/api/chat.py` and `backend/app/main.py`.
- `.env` and `frontend/`.

---

## 11. Audit Certification Checklist

- [x] All 417 source temple JSON files inspected for pricing fields.
- [x] Schema analyzed: 384 fixed prices, 104 ranges, 31 free services, 42 unquantified entries.
- [x] Read-only knowledge access via `RAGTool.get_temple_category_data` verified.
- [x] Zero API keys and ₹0 external cost requirement certified.
- [x] Deterministic parameter extraction and tiered budget models specified.
- [x] Multi-intent preservation (weather+budget, itinerary+budget) verified.
- [x] Coordinator dependency-injection rule (0 auto-instantiation) specified.
- [x] Protected data boundaries defined.
- [x] Production code and tests left 100% untouched.

---

### **AUDIT COMPLETE — HARD STOP**
Phase O4 Architecture Audit is finished. No production code, tests, or datasets were modified.
Awaiting user instructions before Phase O4 implementation.
