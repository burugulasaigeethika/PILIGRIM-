# 📐 PilgrimAI — Complete Mathematical & Calculation Formulas Guide

> **Document Version**: 1.0  
> **Scope**: Complete mathematical derivations, algorithms, scoring functions, and deterministic arithmetic used across the entire PilgrimAI application.  
> **Core Principle**: Zero-hallucination. Arithmetic is strictly computed deterministically in Python rather than delegated to probabilistic LLM approximations.

---

## 📑 Table of Contents
1. [Core Philosophy: Deterministic Computation in PilgrimAI](#1-core-philosophy)
2. [Section 1: Information Retrieval & Hybrid RAG Formulations](#2-section-1-information-retrieval--hybrid-rag-formulations)
   - [1.1 Okapi BM25 Lexical Keyword Scoring](#11-okapi-bm25-lexical-keyword-scoring)
   - [1.2 L2 Vector Normalization & Cosine Similarity](#12-l2-vector-normalization--cosine-similarity)
   - [1.3 Reciprocal Rank Fusion (RRF)](#13-reciprocal-rank-fusion-rrf)
   - [1.4 Cross-Encoder Neural Reranking Logits](#14-cross-encoder-neural-reranking-logits)
   - [1.5 Semantic Domain Guardrail Classification](#15-semantic-domain-guardrail-classification)
   - [1.6 Hierarchical Text Chunking Window Geometry](#16-hierarchical-text-chunking-window-geometry)
3. [Section 2: Spatial Navigation & Itinerary Planning Mechanics](#3-section-2-spatial-navigation--itinerary-planning-mechanics)
   - [2.1 Distance & Duration Metric Conversions](#21-distance--duration-metric-conversions)
   - [2.2 Temporal Representation Arithmetic](#22-temporal-representation-arithmetic)
   - [2.3 Multi-Day Itinerary Partitioning (Quotient-Remainder)](#23-multi-day-itinerary-partitioning-quotient-remainder)
   - [2.4 Multi-Leg Cumulative Route Sums](#24-multi-leg-cumulative-route-sums)
4. [Section 3: Grounded Budget & Cost Optimization Arithmetic](#4-section-3-grounded-budget--cost-optimization-arithmetic)
   - [3.1 Night Estimation Function](#31-night-estimation-function)
   - [3.2 Unit Multiplier Scaling Equations](#32-unit-multiplier-scaling-equations)
   - [3.3 Bounded Interval Arithmetic [Min, Max]](#33-bounded-interval-arithmetic-min-max)
   - [3.4 Accommodation Budget Feasibility Inequality](#34-accommodation-budget-feasibility-inequality)
5. [Section 4: Security, Authentication & Cryptographic Formulations](#5-section-4-security-authentication--cryptographic-formulations)
   - [5.1 Cryptographic Randomness (CSPRNG Entropy)](#51-cryptographic-randomness-csprng-entropy)
   - [5.2 SHA-256 One-Way Cryptographic Digest](#52-sha-256-one-way-cryptographic-digest)
   - [5.3 Temporal Token Expiry (TTL Deltas)](#53-temporal-token-expiry-ttl-deltas)
   - [5.4 Password Key Derivation (Bcrypt)](#54-password-key-derivation-bcrypt)
6. [Section 5: Formula Cheatsheet & Code Reference Table](#6-section-5-formula-cheatsheet--code-reference-table)

---

## 1. Core Philosophy

Large Language Models (LLMs) are probabilistic token predictors, prone to math errors and extrapolation when calculating numbers. 

PilgrimAI enforces **100% Deterministic Arithmetic**:
* Every cost, distance, driving duration, token rank, and similarity score is computed using **exact mathematical formulas in Python runtime code**.
* The LLM's role is restricted to natural language summarization of pre-calculated, verified variables.

```
User Request ──► Python Deterministic Math Engine ──► Verified Numeric Variables ──► Strict Prompt ──► Verified Response
```

---

## 2. Section 1: Information Retrieval & Hybrid RAG Formulations

### 1.1 Okapi BM25 Lexical Keyword Scoring
* **Code Implementation**: `backend/app/rag/bm25.py` (`LocalBM25Manager`)
* **Underlying Library**: `rank_bm25.BM25Okapi`
* **Purpose**: Evaluates exact term matches for deity names, Telugu ritual titles, phone numbers, and pricing numbers that dense semantic vector models frequently overlook.

#### Mathematical Equation:
$$\text{Score}_{\text{BM25}}(D, Q) = \sum_{i=1}^{n} \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

#### Component Derivations:
1. **Inverse Document Frequency (IDF)**:
   Measures how rare or informative query term $q_i$ is across the corpus:
   $$\text{IDF}(q_i) = \ln\left( \frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} + 1 \right)$$
   * $N$: Total number of child chunks indexed across all temples.
   * $n(q_i)$: Number of chunks that contain the token $q_i$.
   * $+0.5$ and $+1$: Robertson-Spärck Jones smoothing to prevent zero or negative values.

2. **Term Frequency Saturation Component**:
   $$\frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1}$$
   * $f(q_i, D)$: Raw occurrence count of token $q_i$ in chunk $D$.
   * $k_1 = 1.5$: Calibrates saturation. As $f(q_i, D) \to \infty$, the term approaches an asymptote of $(k_1 + 1) = 2.5$, preventing keyword stuffing from dominating the score.

3. **Document Length Normalization**:
   $$B = 1 - b + b \cdot \frac{|D|}{\text{avgdl}}$$
   * $|D|$: Number of tokens in chunk $D$.
   * $\text{avgdl}$: Mean token count of all chunks in the corpus.
   * $b = 0.75$: Length penalty weight. If a chunk is shorter than average ($|D| < \text{avgdl}$), $B < 1$, boosting its score; if longer, $B > 1$, dampening its score.

#### Numerical Example:
* Corpus: $N = 1,000$ chunks, $\text{avgdl} = 50$ tokens.
* Term $q = \text{"Abhishekam"}$, appears in $n(q) = 10$ chunks.
* $\text{IDF} = \ln\left(\frac{1000 - 10 + 0.5}{10 + 0.5} + 1\right) = \ln\left(\frac{990.5}{10.5} + 1\right) = \ln(95.33) \approx 4.557$.
* In a chunk $D$ where $|D| = 50$ and $f(q, D) = 2$:
  $$\text{Score} = 4.557 \cdot \frac{2 \cdot 2.5}{2 + 1.5 \cdot (1 - 0.75 + 0.75 \cdot 1)} = 4.557 \cdot \frac{5.0}{3.5} \approx 6.51$$

---

### 1.2 L2 Vector Normalization & Cosine Similarity
* **Code Implementation**: `backend/app/rag/embeddings.py`, `backend/app/rag/vectordb.py`
* **Model**: `sentence-transformers/all-MiniLM-L6-v2` (dimension $d = 384$)
* **Purpose**: Quantifies conceptual semantic proximity (e.g., matching *"where to stay"* with *"dormitory rooms and choultries"*).

#### 1. L2 Euclidean Normalization:
$$\hat{\mathbf{v}} = \frac{\mathbf{v}}{\|\mathbf{v}\|_2} = \frac{\mathbf{v}}{\sqrt{\sum_{i=1}^{384} v_i^2}}$$
* Maps all 384-dimensional dense vectors onto a unit hypersphere ($S^{383}$), where $\|\hat{\mathbf{v}}\|_2 = 1.0$.

#### 2. Cosine Similarity as Dot Product:
$$\text{Sim}(\mathbf{q}, \mathbf{d}) = \frac{\mathbf{q} \cdot \mathbf{d}}{\|\mathbf{q}\|_2 \|\mathbf{d}\|_2} = \sum_{i=1}^{384} \hat{q}_i \cdot \hat{d}_i$$
* **Optimization Benefit**: Because embeddings are pre-normalized during offline ingestion, Qdrant executes rapid hardware-accelerated matrix dot products without runtime square-root operations.
* Range: $[-1.0, 1.0]$, where $1.0$ is perfect semantic identity.

---

### 1.3 Reciprocal Rank Fusion (RRF)
* **Code Implementation**: `backend/app/rag/rrf.py` (`reciprocal_rank_fusion`)
* **Purpose**: Merges and re-ranks top-30 candidates from dense vector search and sparse BM25 search without arbitrary weight tuning.

#### Mathematical Equation:
$$\text{RRF\_Score}(d) = \sum_{m \in M} \frac{1}{k + \text{rank}_m(d)}$$

Where:
* $M = \{\text{Dense Vector Search}, \text{BM25 Keyword Search}\}$.
* $\text{rank}_m(d) \in \{1, 2, \dots, 30\}$: 1-indexed ranking position of document $d$ in retrieval list $m$.
* $k = 60.0$ (`settings.RRF_K`): The Cormack et al. constant that dampens the influence of top ranks so outliers cannot distort the composite score.

#### Rank Comparison Matrix:
| Document | Dense Rank | BM25 Rank | Dense Term $\frac{1}{60 + r_D}$ | BM25 Term $\frac{1}{60 + r_B}$ | Composite RRF Score | Result |
|---|---|---|---|---|---|---|
| **Doc A** (Top in both) | 1 | 1 | $\frac{1}{61} \approx 0.01639$ | $\frac{1}{61} \approx 0.01639$ | **0.03279** | 🥇 **Rank 1** |
| **Doc B** (Top in Dense only) | 1 | Not Found | $\frac{1}{61} \approx 0.01639$ | $0.0$ | **0.01639** | 🥉 **Rank 3** |
| **Doc C** (High in both) | 3 | 4 | $\frac{1}{63} \approx 0.01587$ | $\frac{1}{64} \approx 0.01563$ | **0.03150** | 🥈 **Rank 2** |

---

### 1.4 Cross-Encoder Neural Reranking Logits
* **Code Implementation**: `backend/app/rag/reranker.py` (`LocalCrossEncoderReranker`)
* **Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
* **Purpose**: Evaluates candidate passages using full cross-attention between every token of the query and every token of the candidate passage.

#### Mathematical Formulation:
$$\mathbf{z} = \text{Transformer}\left([\text{CLS}] \circ q_1 \dots q_m \circ [\text{SEP}] \circ d_1 \dots d_p \circ [\text{SEP}]\right)$$
$$s(q, d) = \mathbf{w}^T \mathbf{z}_{[\text{CLS}]} + b$$
* $s(q, d) \in (-\infty, +\infty)$: Unbounded real-valued relevance logit.
* If probability normalization is needed:
  $$P(\text{Relevant} \mid q, d) = \sigma(s) = \frac{1}{1 + e^{-s}}$$

---

### 1.5 Semantic Domain Guardrail Classification
* **Code Implementation**: `backend/app/rag/guardrail.py` (`DomainGuardrail`)
* **Threshold**: $\tau = -3.0$ (`settings.GUARDRAIL_SCORE_THRESHOLD`)
* **Purpose**: Filters out off-topic queries (e.g. general chit-chat, coding, unrelated recipes) before invoking the generative LLM.

#### Step Decision Function:
$$\text{Guardrail}(q) = \begin{cases} 
\text{PASS (Domain Relevant)} & \text{if } \max_{d \in \mathcal{C}} s(q, d) \ge -3.0 \\ 
\text{REJECT (Trigger Refusal)} & \text{if } \max_{d \in \mathcal{C}} s(q, d) < -3.0 
\end{cases}$$

Where $\mathcal{C}$ is the candidate set of the top retrieved passages.

---

### 1.6 Hierarchical Text Chunking Window Geometry
* **Code Implementation**: `backend/app/rag/chunker.py` (`HierarchicalChunker`)
* **Parameters**: Chunk Size $C = 300$, Overlap $O = 50$
* **Purpose**: Slices parent documents into search tokens while preserving sentence boundaries and parent identifiers.

#### Window Geometry Formulas:
$$\text{Stride } S = C - O = 300 - 50 = 250 \text{ characters}$$
$$\text{Chunk}_k \text{ Window Bounds} = [k \cdot S, \; k \cdot S + C], \quad k \in \{0, 1, \dots, N-1\}$$
$$\text{Total Chunks } N = \max\left(1, \; \left\lceil \frac{L - O}{S} \right\rceil\right)$$
where $L$ is the total character length of the raw parent document.

---

## 3. Section 2: Spatial Navigation & Itinerary Planning Mechanics

* **Code Implementation**: `backend/app/agents/itinerary_planning_agent.py`

### 2.1 Distance & Duration Metric Conversions
Raw metrics returned by the Google Routes API navigation integration are converted to standard pilgrimage metrics:

1. **Distance Conversion (Meters to Kilometers)**:
   $$\text{dist}_{\text{km}} = \text{round}\left( \frac{\text{distanceMeters}}{1000.0}, \; 1 \right)$$

2. **Duration Conversion (Seconds to Fractional Minutes)**:
   $$\text{dur}_{\text{minutes}} = \text{round}\left( \frac{\text{durationSeconds}}{60.0}, \; 1 \right)$$

---

### 2.2 Temporal Representation Arithmetic
Converts total integer minutes into human-readable hours and minutes strings:

$$\text{Total Mins} = \text{round}(\text{duration\_minutes})$$
$$\text{Hours } H = \lfloor \text{Total Mins} / 60 \rfloor$$
$$\text{Remaining Minutes } M = \text{Total Mins} \pmod{60}$$

$$\text{Display String} = \begin{cases}
M \text{ min} & \text{if } H = 0 \\
H \text{ hr} & \text{if } H > 0 \text{ and } M = 0 \\
H \text{ hr } M \text{ min} & \text{if } H > 0 \text{ and } M > 0
\end{cases}$$

---

### 2.3 Multi-Day Itinerary Partitioning (Quotient-Remainder)
When a user requests a multi-day itinerary visiting $N$ temples over $D$ days ($D \ge N$), the schedule allocates full days deterministically via Euclidean division:

$$\text{Base Days } B = \left\lfloor \frac{D}{N} \right\rfloor$$
$$\text{Surplus Days } R = D \pmod{N}$$

The days assigned to temple $T_i$ (for $i \in \{0, 1, \dots, N-1\}$) are:
$$\text{Days}(T_i) = B + \begin{cases} 1 & \text{if } i < R \\ 0 & \text{if } i \ge R \end{cases}$$

*Constraint Invariant*: $\sum_{i=0}^{N-1} \text{Days}(T_i) \equiv D$.

---

### 2.4 Multi-Leg Cumulative Route Sums
For multi-destination pilgrimage itineraries with $L$ travel legs:

1. **Total Driving Distance**:
   $$\text{Total Distance (km)} = \text{round}\left( \sum_{l=1}^{L} \text{dist}_{\text{km}}^{(l)}, \; 1 \right)$$

2. **Total Driving Duration**:
   $$\text{Total Duration (mins)} = \text{round}\left( \sum_{l=1}^{L} \text{dur}_{\text{mins}}^{(l)}, \; 1 \right)$$

3. **Day-Trip Round-Trip Multiplier**:
   $$\text{Round-Trip Driving Time} = 2 \times \text{One-Way Leg Duration}$$

---

## 4. Section 3: Grounded Budget & Cost Optimization Arithmetic

* **Code Implementation**: `backend/app/agents/budget_agent.py` (`_calculate_totals`)

### 3.1 Night Estimation Function
Pilgrimage accommodation costs depend on calculated stay duration:

$$\text{nights} = \begin{cases} 
\max(0, \text{params}[\text{"nights"}]) & \text{if nights is explicitly provided} \\
0 & \text{if no accommodation requested / day-trip} \\
\max(0, \text{days} - 1) & \text{if days} > 1 \\
1 & \text{if accommodation explicitly requested and days} = 1 \\
0 & \text{otherwise}
\end{cases}$$

---

### 3.2 Unit Multiplier Scaling Equations
Every item cost in the knowledge registry carries a billing unit:

$$\text{Multiplier}(item) = \begin{cases}
\text{pax} & \text{if unit} = \text{"per person"} \\
\text{rooms} \times \text{nights} & \text{if unit} \in \{\text{"per room per night"}, \text{"per room"}, \text{"per night"}\} \\
\text{pax} \times \text{nights} & \text{if unit} = \text{"per person per night (dormitory)"} \\
1 & \text{if unit} \in \{\text{"per vehicle"}, \text{"flat fee"}\}
\end{cases}$$

$$\text{Scaled Cost}(item) = \text{Base Cost}(item) \times \text{Multiplier}(item)$$

---

### 3.3 Bounded Interval Arithmetic [Min, Max]
To reflect varying room tiers and seva classes without fabricating arbitrary numbers, PilgrimAI maintains mathematical interval bounds throughout all additions:

$$\text{Item Cost Range} = [c_{\min}, \; c_{\max}]$$

For an aggregation of $K$ pilgrimage items:
$$\text{Total Min Cost} = \sum_{k=1}^{K} \left( c_{\min}^{(k)} \times \text{Multiplier}^{(k)} \right)$$
$$\text{Total Max Cost} = \sum_{k=1}^{K} \left( c_{\max}^{(k)} \times \text{Multiplier}^{(k)} \right)$$

$$\text{Final Cost Range} = \left[ \text{Total Min Cost}, \; \text{Total Max Cost} \right]$$

---

### 3.4 Accommodation Budget Feasibility Inequality
When selecting hotel or choultry stays under a user-defined budget limit $B_{\text{limit}}$:

$$\text{Base Fixed Costs} = \text{Total Entry Fees} + \text{Selected Seva Fees} + \text{User Expenses}$$

An accommodation option $A_j$ is deemed feasible if and only if:
$$\text{Base Fixed Costs}_{\min} + \text{Cost}(A_j)_{\min} \le B_{\text{limit}}$$

If all accommodation options exceed $B_{\text{limit}}$, the system selects the lowest-cost available option and raises an explicit budget shortfall warning.

---

## 5. Section 4: Security, Authentication & Cryptographic Formulations

* **Code Implementation**: `backend/app/api/auth.py`, `backend/app/tasks/celery_app.py`

### 5.1 Cryptographic Randomness (CSPRNG Entropy)
Single-use tokens for password resets and email verification use cryptographic random bytes generated directly from the operating system's entropy pool:

$$T_{\text{raw}} = \text{token\_urlsafe}(32)$$
* Entropy: $32 \text{ bytes} \times 8 \text{ bits/byte} = 256 \text{ bits of entropy}$.
* Brute-force complexity: $2^{256} \approx 1.15 \times 10^{77}$ combinations.

---

### 5.2 SHA-256 One-Way Cryptographic Digest
To prevent plain-text database leaks, tokens are hashed before storage in MongoDB:

$$H = \text{SHA-256}(T_{\text{raw}}) = \text{Merkle-Damg\aa{}rd}\left(T_{\text{raw}}, \text{IV}\right) \in \{0, 1\}^{256}$$
$$\text{Stored Digest} = \text{hex}(H) \quad (64 \text{ hexadecimal characters})$$

* Verification invariant:
  $$\text{Valid} \iff \text{SHA-256}(T_{\text{input}}) = H_{\text{stored}} \quad \text{and} \quad t_{\text{now}} \le t_{\text{expires\_at}}$$

---

### 5.3 Temporal Token Expiry (TTL Deltas)
Token expiration is verified against UTC timestamps:

$$t_{\text{expires\_at}} = t_{\text{current\_utc}} + \Delta t$$

| Token Purpose | Delta $\Delta t$ | Expiry Invariant Check |
|---|---|---|
| **Password Reset Token** | 30 minutes (`timedelta(minutes=30)`) | $t_{\text{now}} < t_{\text{request}} + 1800 \text{ s}$ |
| **Email Verification Token** | 24 hours (`timedelta(hours=24)`) | $t_{\text{now}} < t_{\text{request}} + 86400 \text{ s}$ |

---

### 5.4 Password Key Derivation (Bcrypt)
Passwords use Bcrypt key derivation with per-user salt and adaptive work factor:

$$\text{Hash} = \text{Bcrypt}(P, \; \text{salt}, \; \text{cost} = 12)$$
* Salt: 128-bit random salt protecting against rainbow table attacks.
* Iterations: $2^{\text{cost}} = 2^{12} = 4,096$ rounds of Blowfish encryption.

---

## 6. Section 5: Formula Cheatsheet & Code Reference Table

| Formula / Algorithm | Symbolic Notation | Implementation File | Primary Parameters |
|---|---|---|---|
| **BM25 Lexical Score** | $\text{Score}_{\text{BM25}}(D, Q)$ | `backend/app/rag/bm25.py` | $k_1 = 1.5, \; b = 0.75$ |
| **Inverse Document Freq** | $\text{IDF}(q_i) = \ln\left(\frac{N - n + 0.5}{n + 0.5} + 1\right)$ | `backend/app/rag/bm25.py` | Corpus chunks $N$ |
| **L2 Norm Embeddings** | $\hat{\mathbf{v}} = \mathbf{v} / \|\mathbf{v}\|_2$ | `backend/app/rag/embeddings.py` | Dimension $d = 384$ |
| **Cosine Dot Product** | $\sum_{i=1}^{384} \hat{q}_i \hat{d}_i$ | `backend/app/rag/vectordb.py` | Space: Unit sphere $S^{383}$ |
| **Reciprocal Rank Fusion** | $\sum \frac{1}{k + \text{rank}(d)}$ | `backend/app/rag/rrf.py` | $k = 60.0$, top-$k = 30$ |
| **Neural Logit Score** | $s(q, d) = \mathbf{w}^T \mathbf{z} + b$ | `backend/app/rag/reranker.py` | `ms-marco-MiniLM-L-6-v2` |
| **Guardrail Threshold** | $s \ge -3.0$ | `backend/app/rag/guardrail.py` | $\tau = -3.0$ |
| **Chunking Stride** | $\text{Stride} = C - O$ | `backend/app/rag/chunker.py` | $C = 300, \; O = 50$ |
| **Distance Conversion** | $\text{dist} = \text{round}(m / 1000, 1)$ | `backend/app/agents/itinerary_planning_agent.py` | Metric: Kilometers |
| **Duration Conversion** | $\text{dur} = \text{round}(s / 60, 1)$ | `backend/app/agents/itinerary_planning_agent.py` | Metric: Minutes |
| **Euclidean Day Allocation** | $\lfloor D / N \rfloor + (1 \text{ if } i < D \bmod N)$ | `backend/app/agents/itinerary_planning_agent.py` | Partition: $D \ge N$ |
| **Night Estimation** | $\max(0, \text{days} - 1)$ | `backend/app/agents/budget_agent.py` | Unit: Nights |
| **Interval Addition** | $[\sum c_{\min}, \; \sum c_{\max}]$ | `backend/app/agents/budget_agent.py` | Unit: INR (₹) |
| **CSPRNG Entropy** | $\text{token\_urlsafe}(32)$ | `backend/app/api/auth.py` | 256 bits entropy |
| **SHA-256 Digest** | $\text{SHA-256}(T_{\text{raw}})$ | `backend/app/api/auth.py` | 32-byte digest |
| **Expiry Delta** | $t_{\text{current}} + \Delta t$ | `backend/app/api/auth.py` | 30 min / 24 hr |
