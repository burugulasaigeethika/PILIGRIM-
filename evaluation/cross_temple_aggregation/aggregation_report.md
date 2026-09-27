# Cross-Temple Aggregation Capability Evaluation Report

## 1. Executive Summary
- **Total Test Cases**: 6
- **Passed Test Cases**: 6 (100.0%)
- **Precision**: 100.0%
- **Recall**: 100.0%
- **F1 Score**: 1.0000
- **Exact Set Accuracy**: 100% (Exact 11 river-bank temples discovered dynamically)
- **Source Grounding Rate**: 100.0% (Every match backed by verified JSON source evidence)
- **Duplicate Rate**: 0.0%

---

## 2. Benchmark Metrics

| Metric | Measured Value | Target / Requirement | Status |
| :--- | :---: | :---: | :---: |
| **Temples Searched** | 20 | All 20 temple folders | ✅ PASSED |
| **River Bank Matches** | **11 Temples** | Dynamic extraction (11 genuine) | ✅ PASSED |
| **Precision** | **1.0000** | 100% | ✅ PASSED |
| **Recall** | **1.0000** | 100% | ✅ PASSED |
| **F1 Score** | **1.0000** | 1.0000 | ✅ PASSED |
| **Duplicate Rate** | **0.0%** | 0.0% | ✅ PASSED |
| **Normal Query Isolation** | Top-3 preserved | `FINAL_RERANK_TOP_K = 3` | ✅ PASSED |
| **Complete Single-Temple List** | 100% Preserved | Full parent context | ✅ PASSED |
| **Avg Aggregation Latency** | 5.53 ms | < 100 ms (deterministic) | ✅ PASSED |

---

## 3. Discovered River-Bank Temples & Grounded Evidence

1. **Ahobilam** — River: Bhavanashini River (Pavanasini River) (`ahobilam/river_bank.json`)
2. **Badrachalam** — River: River Godavari (Dakshina Vahini) (`badrachalam/river_bank.json`)
3. **Basara** — River: River Godavari (`basara/river_bank.json`)
4. **Dharmapuri** — River: Godavari (Dakshina Vahini) (`dharmapuri/river_bank.json`)
5. **Edupayal** — River: Manjeera River (Edu Payalu Confluence) (`edupayal/river_bank.json`)
6. **Jogulamba(New)** — River: Tungabhadra River & Krishna River (`jogulamba(new)/river_bank.json`)
7. **Kaleshvaram** — River: Dakshina Triveni Sangamam (`kaleshvaram/river_bank.json`)
8. **Medaram** — River: Jampanna Vagu (`medaram/river_bank.json`)
9. **Srisaila** — River: Krishna River (Patalaganga) (`srisaila/river_bank.json`)
10. **Veera Satyanarayana** — River: Pampa River (`veera satyanarayana/river_bank.json`)
11. **Vemulavada** — River: Mulavagu stream (tributary of Godavari River) (`vemulavada/river_bank.json`)

---

## 4. Test Case Execution Details

### [PASSED] `AGG_RIVER_BANK_ALL`: "List all the temples that have river bank"
- **Query Routing Type**: `cross_temple_aggregation`
- **Retrieved Chunks**: `11`
- **Latency**: `12.31 ms`
- **Sources**: `['ahobilam/river_bank.json', 'badrachalam/river_bank.json', 'basara/river_bank.json', 'dharmapuri/river_bank.json', 'edupayal/river_bank.json', 'jogulamba(new)/river_bank.json', 'kaleshvaram/river_bank.json', 'medaram/river_bank.json', 'srisaila/river_bank.json', 'veera satyanarayana/river_bank.json', 'vemulavada/river_bank.json']`
- **Answer Output**:
```
Based on the temple knowledge base, the following **11 temples** have confirmed **River Bank** information:

1. **Ahobilam** — River: Bhavanashini River (Pavanasini River) (Ghat: Raktha Kundam)
2. **Badrachalam** — River: River Godavari (Dakshina Vahini) (Ghat: Godavari Bathing Ghats & Kalyana Katta)
3. **Basara** — River: River Godavari (Ghat: Basara Godavari River Bathing Ghat)
4. **Dharmapuri** — River: Godavari (Dakshina Vahini) (Ghat: Dharmapuri Godavari River Bathing Ghat)
5. **Edupayal** — River: Manjeera River (Edu Payalu Confluence) (Ghat: Edupayala Seven Streams River Ghats)
6. **Jogulamba(New)** — River: Tungabhadra River & Krishna River (Sacred Confluence / Tungabhadra–Krishna Sangam) (Ghat: Jogulamba River Ghat)
7. **Kaleshvaram** — River: Dakshina Triveni Sangamam (River Godavari, River Pranahita, and subterranean River Saraswati) (Ghat: Triveni Sangam Bathing Ghats)
8. **Medaram** — River: Jampanna Vagu (Ghat: Jampanna Vagu Main Bathing Ghats)
9. **Srisaila** — River: Krishna River (Patalaganga) (Ghat: Patalaganga Bathing Ghat)
10. **Veera Satyanarayana** — River: Pampa River (Ghat: Pampa River Foothills Boating & Ghat Point)
11. **Vemulavada** — River: Mulavagu stream (tributary of Godavari River) & Dharma Gundam (Pushkarni) / Gudicheruvu (Ghat: Dharma Gundam Bathing Steps)
```

---
### [PASSED] `AGG_RIVER_WHICH_TEMPLES`: "Which temples have a river?"
- **Query Routing Type**: `cross_temple_aggregation`
- **Retrieved Chunks**: `11`
- **Latency**: `2.18 ms`
- **Sources**: `['ahobilam/river_bank.json', 'badrachalam/river_bank.json', 'basara/river_bank.json', 'dharmapuri/river_bank.json', 'edupayal/river_bank.json', 'jogulamba(new)/river_bank.json', 'kaleshvaram/river_bank.json', 'medaram/river_bank.json', 'srisaila/river_bank.json', 'veera satyanarayana/river_bank.json', 'vemulavada/river_bank.json']`
- **Answer Output**:
```
Based on the temple knowledge base, the following **11 temples** have confirmed **River Bank** information:

1. **Ahobilam** — River: Bhavanashini River (Pavanasini River) (Ghat: Raktha Kundam)
2. **Badrachalam** — River: River Godavari (Dakshina Vahini) (Ghat: Godavari Bathing Ghats & Kalyana Katta)
3. **Basara** — River: River Godavari (Ghat: Basara Godavari River Bathing Ghat)
4. **Dharmapuri** — River: Godavari (Dakshina Vahini) (Ghat: Dharmapuri Godavari River Bathing Ghat)
5. **Edupayal** — River: Manjeera River (Edu Payalu Confluence) (Ghat: Edupayala Seven Streams River Ghats)
6. **Jogulamba(New)** — River: Tungabhadra River & Krishna River (Sacred Confluence / Tungabhadra–Krishna Sangam) (Ghat: Jogulamba River Ghat)
7. **Kaleshvaram** — River: Dakshina Triveni Sangamam (River Godavari, River Pranahita, and subterranean River Saraswati) (Ghat: Triveni Sangam Bathing Ghats)
8. **Medaram** — River: Jampanna Vagu (Ghat: Jampanna Vagu Main Bathing Ghats)
9. **Srisaila** — River: Krishna River (Patalaganga) (Ghat: Patalaganga Bathing Ghat)
10. **Veera Satyanarayana** — River: Pampa River (Ghat: Pampa River Foothills Boating & Ghat Point)
11. **Vemulavada** — River: Mulavagu stream (tributary of Godavari River) & Dharma Gundam (Pushkarni) / Gudicheruvu (Ghat: Dharma Gundam Bathing Steps)
```

---
### [PASSED] `AGG_ACCOMMODATION_ALL`: "List all temples with accommodation"
- **Query Routing Type**: `cross_temple_aggregation`
- **Retrieved Chunks**: `20`
- **Latency**: `2.1 ms`
- **Sources**: `['ahobilam/accommodation.json', 'badrachalam/accommodation.json', 'balkampet/accommodation.json', 'basara/accommodation.json', 'birla mandir/accommodation.json', 'chilkur/accommodation.json', 'dharmapuri/accommodation.json', 'edupayal/accommodation.json', 'jogulamba(new)/accommodation.json', 'kaleshvaram/accommodation.json', 'karmanghat/accommodation.json', 'medaram/accommodation.json', 'ramappa/accommodation.json', 'srisaila/accommodation.json', 'thousand pillar/accommodation.json', 'ttd/accommodation.json', 'ujjaini/accommodation.json', 'veera satyanarayana/accommodation.json', 'vemulavada/accommodation.json', 'yadadri/accommodation.json']`
- **Answer Output**:
```
Based on the temple knowledge base, the following **20 temples** have confirmed **Accommodation** information:

1. **Ahobilam** — Offers 4 accommodation options
2. **Badrachalam** — Offers 7 accommodation options
3. **Balkampet** — Offers 3 accommodation options
4. **Basara** — Offers 4 accommodation options
5. **Birla Mandir** — Offers 2 accommodation options
6. **Chilkur** — Offers 4 accommodation options
7. **Dharmapuri** — Offers 1 accommodation options
8. **Edupayal** — Offers 6 accommodation options
9. **Jogulamba(New)** — Offers 6 accommodation options
10. **Kaleshvaram** — Offers 4 accommodation options
11. **Karmanghat** — Offers 7 accommodation options
12. **Medaram** — Offers 7 accommodation options
13. **Ramappa** — Offers 5 accommodation options
14. **Srisaila** — Offers 4 accommodation options
15. **Thousand Pillar** — Offers 9 accommodation options
16. **Ttd** — Offers 48 accommodation options
17. **Ujjaini** — Offers 4 accommodation options
18. **Veera Satyanarayana** — Offers 12 accommodation options
19. **Vemulavada** — Offers 5 accommodation options
20. **Yadadri** — Offers 8 accommodation options
```

---
### [PASSED] `SPECIFIC_TEMPLE_RIVER_DHARMAPURI`: "Does Dharmapuri have a river bank?"
- **Query Routing Type**: `specific_temple_normal`
- **Retrieved Chunks**: `3`
- **Latency**: `6229.39 ms`
- **Sources**: `['dharmapuri/river_bank.json']`
- **Answer Output**:
```
Yes, Dharmapuri has a river bank.
```

---
### [PASSED] `NORMAL_TARGETED_PRICE`: "What is the price of Abhishekam in Dharmapuri?"
- **Query Routing Type**: `normal_targeted`
- **Retrieved Chunks**: `3`
- **Latency**: `3676.75 ms`
- **Sources**: `['dharmapuri/faq.json', 'dharmapuri/prasadam.json', 'dharmapuri/sevas.json']`
- **Answer Output**:
```
The price of Abhishekam in Dharmapuri is ₹500.
```

---
### [PASSED] `SINGLE_TEMPLE_COMPLETE_LIST`: "What are all the sevas in Dharmapuri?"
- **Query Routing Type**: `single_temple_complete_list`
- **Retrieved Chunks**: `1`
- **Latency**: `44465.35 ms`
- **Sources**: `['dharmapuri/sevas.json']`
- **Answer Output**:
```
Based on the provided context, the sevas in Dharmapuri are:

1. Abhishekam - Telugu Name: అభిషేకం
   Price: ₹500
   Timing: from 6:00 AM

2. Tulasi Visheṣārchana - Telugu Name: తులసి విశేషార్చన
   Price: ₹500
   Timing: from 8:00 AM

3. Sahasranamas / Korika Nivṛtti - Telugu Name: సహస్రనామాలు / కోరిక నివృత్తి
   Price: ₹50
   Timing: Daily during Archana slots
   Description: Chanting of Sahasranamas and fulfillment of vows

4. Gokṣanāma Harati - Telugu Name: గోక్షణామ హారతి
   Price: ₹200
   Timing: Daily during Archana slots
   Description: Special Harati ritual

5. Odi Biyyam - Telugu Name: ఒడి బియ్యం
   Price: ₹50
   Timing: Daily during Archana slots
   Description: Traditional ritual offering of rice

6. Kumkuma Archana - Telugu Name: కుంకుమ అర్చన
   Price: ₹200
   Timing: Daily during Archana slots
   Description: Kumkuma Archana ritual

7. Pulihora Bhogam / Dadhojana Bhogam - Telugu Name: పులిహోర భోగం / దద్ధోజన భోగం
   Price: ₹300
   Timing: at 10:00 AM
   Description: Special food offerings of Pulihora or Dadhojana served at 10:00 AM

8. Bōrela Bhogam - Telugu Name: బోరెల భోగం
   Price: ₹500
   Timing: at 12:00 noon
   Description: Borela sweet food offering served at 12:00 noon

9. Veda Aashirvachanam - Telugu Name: వేద ఆశీర్వచనం
   Price: ₹500
   Timing: Daily during Archana slots
   Description: Vedic blessings by temple priests

These are all the sevas available in Dharmapuri based on the provided context.
```

---
