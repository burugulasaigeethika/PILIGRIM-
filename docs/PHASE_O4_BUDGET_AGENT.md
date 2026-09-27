# Phase O4 — Budget Agent Documentation

## 1. Objective & Scope

Phase O4 introduces the **`BudgetAgent`** (`name = "budget"`) to the PilgrimAI ecosystem, providing deterministic, mathematically grounded pilgrimage budget calculations.

**Key Boundaries & Constraints**:
- **Strict Scope**: Implements ONLY `BudgetAgent`. Does NOT implement `LiveNavigationAgent` (O5), `VoiceMultilingualAgent` (O6), or broader Phase O7 integrations.
- **Zero Hallucination / Zero Fabrication**: Absolute prohibition against hardcoded amounts or manufactured tiers. No generic ₹100–₹200 incidental fee, no fabricated ₹150–₹250 food allowance, no manufactured ₹500–₹1,000 accommodation, and no artificial "Economy / Standard / Premium" tiers.
- **Explicit Provenance**: Every line item carries an explicit `CostProvenance` (`VERIFIED`, `USER_PROVIDED`, `CALCULATED`, `ESTIMATE`, `UNAVAILABLE`).
- **Data & Model Safety**: Zero modifications to Qdrant vector database, BM25 index, evaluation datasets, or the 417 source temple JSON files. Zero new API keys or external model dependencies.

---

## 2. End-to-End Architecture

```text
User Query (e.g., "Estimate pilgrimage cost for 4 people visiting Yadadri for 2 days")
    ↓
/chat Endpoint (FastAPI)
    ↓
MasterAgentCoordinator (Receives budget_agent via Dependency Injection)
    ↓
AgentRouter (Deterministic Keyword & Intent Classifier)
    ↓
BudgetAgent (name="budget", inherits BaseAgent)
    ↓
Parameter Extraction (Pax count, duration/nights, requested sevas, user-provided costs)
    ↓
RAGTool.get_temple_category_data(temple, category) [Exclusive RAG Boundary]
    ↓
Deterministic Price Parsing & Unit Safety (₹, Rs., INR, ranges, free, unquantified)
    ↓
Mathematical Totaling (Range preservation [min, max], unit multiplication per person/night)
    ↓
Section 16 Structured Markdown Generation (Verified, User-Provided, Unavailable, Totals)
    ↓
AgentResponse (sources, grounding_score, budget metadata)
    ↓
ResponseAggregator / Multi-Intent Pipeline
    ↓
ChatResponse (FastAPI JSON response)
```

---

## 3. Strict Grounding & Anti-Hallucination Discipline

### 3.1 Provenance Model (`CostProvenance`)

Every expense item is tracked with a strict typed provenance:

| Provenance | Meaning | Calculation Behavior |
|:---|:---|:---|
| `VERIFIED` | Exact amount extracted from verified RAG temple records (`darshan`, `sevas`, `accommodation`, `prasadam`). | Multiplied by pax/nights when unit matches (`per_person`, `per_night`). |
| `USER_PROVIDED` | Explicit expense amount supplied by the user in the prompt (e.g., "Travel: ₹1,500"). | Added to total without altering user specification. |
| `CALCULATED` | Mathematically derived total from verified or user-provided items. | Computed via deterministic summation; preserves ranges `[min, max]`. |
| `ESTIMATE` | Controlled range derived with clear documented assumptions. | Used only with explicit basis. |
| `UNAVAILABLE` | Required service mentioned or implied but lacks quantified pricing in source records. | **Excluded from monetary total**; explicitly surfaced under `Costs Not Available` with on-site devasthanam counter disclosure. |

### 3.2 Prohibition of Manufactured Tiers
The agent does not generate speculative "Economy", "Standard", or "VIP" tiers unless the temple's verified dataset explicitly provides distinct tiered entries (e.g. VIP break darshan vs free general darshan). No speculative expenses are added to fill out a budget.

### 3.3 Free Darshan & Prasadam Rules
- When darshan is free (e.g., "Free general darshan", "Sarva Darshan"), it is recorded with min/max = 0 and provenance `VERIFIED`.
- Free Annadanam is recorded with min/max = 0 and provenance `VERIFIED`.

---

## 4. Deterministic Price Parsing & Unit Safety

The parser `parse_price_text(text, default_category)` deterministically extracts monetary values from free-form RAG text:

1. **Currency Symbols**: Matches `₹`, `Rs\.?`, `INR`, `rupees`.
2. **Ranges**: Detects hyphenated or slash ranges (e.g., `"₹100 - ₹200"`, `"Rs 500 to 1000"`), preserving `[min, max]`.
3. **Free Indicators**: Recognizes `"free"`, `"complimentary"`, `"no charge"`, `"no fee"`, `"nil"`, returning `[0.0, 0.0]`.
4. **Unquantified Patterns**: Identifies non-numeric indicators such as `"as per tariff"`, `"variable"`, `"nominal"`, `"on donation"`, `"contact devasthanam"`, returning `provenance = UNAVAILABLE`.
5. **Unit Detection**:
   - `per_person`: Matches `"per person"`, `"per head"`, `"per devotee"`, `"each"`.
   - `per_night`: Matches `"per night"`, `"per day"`, `"per room"`.
   - `per_ticket`: Matches `"per ticket"`, `"per seva"`.
   - `fixed`: Flat fee per booking/batch.

### Unit Safety Rules
- Items with unit `per_person` are multiplied by devotee count ($N$).
- Items with unit `per_night` are multiplied by nights count ($D$).
- Items with unit `fixed` are added once regardless of devotee count.
- Flat accommodation room tariffs are added per room/night, avoiding erroneous per-person multiplication unless designated per head.

---

## 5. Parameter Extraction

The parameter extractor parses user prompts for pilgrimage logistics:
- **Devotee Count (Pax)**:
  - Numeric regex: `"4 people"`, `"2 persons"`, `"3 devotees"`, `"adults: 2, children: 1"`.
  - Phrase patterns: `"family of 4"` $\rightarrow$ 4.
  - Word numbers: `"two people"` $\rightarrow$ 2, `"three persons"` $\rightarrow$ 3.
  - Default: 1 devotee (disclosed in Assumptions if defaulted).
- **Duration & Nights**:
  - Detects days: `"2 days"` $\rightarrow$ 1 night.
  - Detects nights: `"2 nights"` $\rightarrow$ 2 nights.
  - Day-trip detection: `"day trip"`, `"1 day"` $\rightarrow$ 0 nights.
- **Specific Sevas**:
  - Matches specific seva names from query (e.g., `"Kalyanam"`, `"Abhishekam"`, `"Special Darshan"`).
  - When a specific seva is targeted, default entry/prasadam items are suppressed to maintain laser focus on the user's specific query.
- **User-Provided Amounts**:
  - Extracts user-stated figures for travel, transport, cab, fuel, hotel, food, etc.
  - Formatted into `BudgetItem` with `provenance = USER_PROVIDED`.

---

## 6. RAG Boundary & Architectural Compliance

### 6.1 Exclusive RAG Tool Access
The `BudgetAgent` never accesses the file system directly, never imports raw JSON files, and never makes direct queries to the Qdrant vector database or BM25 index. All data retrieval goes through:

```python
RAGTool.get_temple_category_data(temple_name, category)
```

Categories fetched:
- `darshan` (Entry types, ticket prices, timings)
- `sevas` (Ritual prices, tickets)
- `accommodation` (Guesthouses, choultries, room tariffs)
- `prasadam` (Laddus, pulihora, annadanam)

### 6.2 Temple Identifier Resolution
The agent canonicalizes user temple names and query aliases using `TEMPLE_CANONICAL_MAP`:
- `"Basara"` $\rightarrow$ `"basara_gnana_saraswathi"`
- `"Yadagirigutta"` $\rightarrow$ `"yadadri"`
- Fallbacks allow querying both canonical folder IDs and short names.

### 6.3 Coordinator Dependency Injection
The `MasterAgentCoordinator` adheres strictly to dependency injection:

```python
class MasterAgentCoordinator:
    def __init__(
        self,
        rag_tool: Optional[Any] = None,
        temple_info_agent: Optional[Any] = None,
        comparison_agent: Optional[Any] = None,
        aggregation_agent: Optional[Any] = None,
        itinerary_agent: Optional[Any] = None,
        live_weather_agent: Optional[Any] = None,
        budget_agent: Optional[Any] = None,
        enable_grounding_validator: bool = True,
    ):
        ...
        self.budget_agent = budget_agent  # Zero auto-instantiation
```

---

## 7. Routing & Multi-Intent Protection

### 7.1 Router Modifications
The `AgentRouter` was minimally updated to support budget queries without degrading existing agent capabilities:
- **Priority 3 Multi-Temple Protection**: Queries mentioning $\ge 2$ temples previously defaulted to `comparison`. Added `and not is_budget_syntax` so multi-temple budget requests route cleanly to `budget`.
- **Comparison Query Protection**: Queries containing comparison attribute patterns (e.g., `"Compare seva costs between Yadadri and Basara"`) are preserved for `ComparisonAgent`.
- **Priority 6.6 Budget Agent Routing**: Directs single and multi-temple budget queries to `budget`.

### 7.2 Multi-Intent Pipeline
- Budget queries combined with weather (e.g. `"What is the weather and seva cost at Yadadri?"`) decompose into parallel execution for `live_weather` and `budget`, aggregating seamlessly in `ResponseAggregator`.
- Budget queries combined with itinerary (e.g. `"Plan a 2-day trip to Yadadri with budget"`) decompose into `itinerary` and `budget`.

---

## 8. Output Format Specification

The response follows the standardized Section 16 format:

```markdown
### Pilgrimage Budget: Yadadri (4 Devotees, 1 Night)

#### Verified Costs (Temple Records)
- Special Darshan: ₹100 per person × 4 = ₹400 [VERIFIED]
- Suprabhata Seva: ₹200 per person × 4 = ₹800 [VERIFIED]
- Standard AC Room: ₹1,000 per night [VERIFIED]

#### User-Provided Expenses
- Travel / Cab: ₹2,000 (as specified) [USER_PROVIDED]

#### Costs Not Available in Verified Records
- Food / Meals: Exact devasthanam canteen prices not quantified in records. Free Annadanam available during scheduled timings; verify counter on-site [UNAVAILABLE]

---
#### Total Budget Summary
- **Total Estimated Budget**: ₹4,200.00
- **Total Range**: ₹4,200.00 (Exact verified & user items)

> **Assumptions**: 4 Devotees, 1 Night stay.
> **Note**: Items marked [UNAVAILABLE] are excluded from the numeric total. Please confirm exact devasthanam counter tariffs upon arrival.
```

---

## 9. Verification & Certification Results

### 9.1 Test Suite Summary
The test suite in `tests/test_budget_agent.py` contains **55 offline unit and integration tests**:

1. **Deterministic Parser Tests**:
   - Currency symbol extraction (₹, Rs, INR).
   - Price range handling (`[min, max]`).
   - Free/complimentary darshan and prasadam parsing.
   - Unquantified phrase handling (`"as per tariff"` $\rightarrow$ `UNAVAILABLE`).
   - Unit multiplier recognition (`per_person`, `per_night`, `fixed`).
2. **Parameter Extractor Tests**:
   - Extraction of devotee counts (numbers, words, family phrases).
   - Extraction of durations (days, nights, day-trips).
   - Extraction of user-provided expenses (travel, food, cab).
3. **Budget Calculation Tests**:
   - Deterministic summation for single and multiple devotees.
   - Range preservation across multiple line items.
   - Specific seva query isolation.
   - Exclusion of `UNAVAILABLE` items from numerical totals.
4. **RAG Boundary & Anti-Hallucination Tests**:
   - Exclusive use of `RAGTool.get_temple_category_data`.
   - Handling of missing categories without fabricating estimates.
   - Controlled failure on unknown or invalid temples.
5. **Coordinator & Router Integration Tests**:
   - Dependency injection without auto-instantiation.
   - Priority routing for single-temple and multi-temple budget queries.
   - Protection of `ComparisonAgent` on comparison queries.
   - Multi-intent pipeline integration (`budget + weather`).

### 9.2 Regression Test Status
- Baseline regression: 404/404 passing.
- Phase O4 test suite: 55/55 passing.
- Total combined: **459/459 tests passing (100% green)**.

### 9.3 Source Dataset SHA-256 Integrity
All 417 source temple JSON files across all 7 canonical temple directories were verified against pre-implementation SHA-256 hashes:
- **Total Source Files**: 417
- **Mismatches / Modifications**: **0 (100% byte-for-byte identical)**
