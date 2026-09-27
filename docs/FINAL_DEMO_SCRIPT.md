# PilgrimAI — Final Demonstration Script

This script provides an ordered demonstration sequence of 12 representative queries showcasing the core capabilities and architectural features of PilgrimAI.

---

### Demonstration Query Sequence

#### 1. Targeted Factual Query (Timings)
- **Question**: `"What are the temple timings at Bhadrachalam?"`
- **Expected Behavior**: Returns exact morning (4:30 AM – 1:00 PM) and evening (3:00 PM – 9:00 PM) hours.
- **Architectural Feature**: Hybrid Qdrant + BM25 Top-3 retrieval (`FINAL_RERANK_TOP_K = 3`), `AnswerScopeController` targeted fact prompt, 0% unrelated category dumping.

#### 2. Exact Numerical Extraction (Pricing)
- **Question**: `"What is the price of Abhishekam in Dharmapuri?"`
- **Expected Behavior**: Returns `₹500` with seva name and exact price preservation.
- **Architectural Feature**: Precision fact grounding with currency preservation.

#### 3. Complete Exhaustive List (Sevas)
- **Question**: `"What are all the sevas in Dharmapuri?"`
- **Expected Behavior**: Exhaustively enumerates all 20+ sevas without Top-3 truncation.
- **Architectural Feature**: `KnowledgeRegistry` exhaustive parent resolution with zero missing items.

#### 4. Complete Exhaustive List (Festivals)
- **Question**: `"List all festivals celebrated at Basara."`
- **Expected Behavior**: Returns complete list of festivals (Vasant Panchami, Vyasa Purnima, Navaratri, Maha Shivaratri, etc.).
- **Architectural Feature**: Complete-category route bypassing Top-K truncation limits.

#### 5. Cross-Temple Positive Aggregation (River Banks)
- **Question**: `"Which temples have a river bank?"`
- **Expected Behavior**: Dynamically evaluates all 20 temples and lists the exact 11 temples with confirmed river banks/ghats (Godavari, Krishna, Bhavanashini, etc.).
- **Architectural Feature**: 20-temple dynamic scan via `CrossTempleAggregationAgent` and `CompletenessValidator`.

#### 6. Cross-Temple Negative Aggregation (Wheelchair Limitations)
- **Question**: `"Which temples don't have wheelchair facilities?"`
- **Expected Behavior**: Confirms the 7 temples with verified physical/topographical barriers and distinguishes unrecorded information.
- **Architectural Feature**: 3-tier partitioning (`CONFIRMED_UNAVAILABLE` vs `INFORMATION_NOT_AVAILABLE`).

#### 7. Multi-Category Inquiry (Accommodation + Dining)
- **Question**: `"What accommodation and restaurants are available near Dharmapuri?"`
- **Expected Behavior**: Outputs structured sections for both topics without category starvation.
- **Architectural Feature**: Multi-category balanced context partitioning.

#### 8. Single-Temple Facility Query (Wheelchair Assistance)
- **Question**: `"Does Dharmapuri have wheelchair facilities?"`
- **Expected Behavior**: Accurately explains available wheelchair assistance and ramps at the temple.
- **Architectural Feature**: Targeted facility grounding.

#### 9. Contact & Emergency Inquiries
- **Question**: `"What is the contact number of Basara Temple?"`
- **Expected Behavior**: Returns verified phone numbers and trust email addresses.
- **Architectural Feature**: Contact entity extraction and isolation.

#### 10. Broad Temple Overview
- **Question**: `"Tell me everything about Dharmapuri Temple."`
- **Expected Behavior**: Generates a structured multi-paragraph summary covering history, timings, sevas, and architecture.
- **Architectural Feature**: Priority-budgeted context construction ($k \le 6$).

#### 11. Grounded Refusal for Non-Existent Entity
- **Question**: `"Does Dharmapuri have a helicopter launch pad?"`
- **Expected Behavior**: Grounded refusal: *"I could not find this information in the temple knowledge base."*
- **Architectural Feature**: Entity existence verification in `AnswerGroundingValidator` preventing hallucinations.

#### 12. Cross-Temple Isolation Test
- **Question**: `"Tell me the history of Yadadri."`
- **Expected Behavior**: Focuses exclusively on Lord Lakshmi Narasimha Swamy and Yadagiri hillock without mentioning Bhadrachalam or Basara.
- **Architectural Feature**: Single-temple isolation filter with 0.0% cross-temple bleed.
