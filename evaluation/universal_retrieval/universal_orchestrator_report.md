# Universal Local Retrieval Orchestrator Benchmark Report

## 1. Executive Summary
- **Evaluation Date**: 2026-08-25 22:20:43
- **Total Test Archetypes Evaluated**: 13
- **Passed Test Archetypes**: 13 / 13 (100.0%)
- **Targeted Baseline Invariance**: 100% Preserved (Top-3 Path)
- **Local Environment**: 100% Local / Offline (Qdrant + BM25 + CrossEncoder + Ollama Qwen2.5)

---

## 2. Benchmark Query Results

| ID | Query | Retrieval Mode | Exhaustive | Sources | Latency (ms) | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `1_TARGETED_SEVA_PRICE` | *What is the price of Abhishekam in Dharmapuri?* | `targeted` | `False` | 3 | 3804.08 ms | ✅ PASSED |
| `2_COMPLETE_SEVAS_DHARMAPURI` | *What are all the sevas in Dharmapuri?* | `complete_category` | `True` | 1 | 43878.21 ms | ✅ PASSED |
| `3_COMPLETE_FESTIVALS_BASARA` | *List all festivals at Basara.* | `complete_category` | `True` | 1 | 19416.88 ms | ✅ PASSED |
| `4_AGGREGATION_RIVER_POSITIVE` | *List all temples that have a river bank.* | `cross_temple_aggregation` | `True` | 11 | 10.54 ms | ✅ PASSED |
| `5_AGGREGATION_WHEELCHAIR_NEGATIVE` | *List all temples that don't have wheelchair facilities.* | `cross_temple_aggregation` | `True` | 7 | 8.99 ms | ✅ PASSED |
| `6_AGGREGATION_ACCOMMODATION_POSITIVE` | *Which temples have accommodation?* | `cross_temple_aggregation` | `True` | 20 | 7.42 ms | ✅ PASSED |
| `7_AGGREGATION_RESTAURANTS_NEGATIVE` | *Which temples don't have restaurants?* | `cross_temple_aggregation` | `True` | 0 | 6.3 ms | ✅ PASSED |
| `8_MULTI_CATEGORY_ACCOMMODATION_RESTAURANTS` | *What accommodation and restaurants are available near Dharmapuri?* | `multi_category` | `True` | 2 | 7493.6 ms | ✅ PASSED |
| `9_TARGETED_TIMINGS` | *What are the timings of Dharmapuri Temple?* | `targeted` | `False` | 3 | 13010.94 ms | ✅ PASSED |
| `10_TARGETED_HISTORY` | *Tell me the history of Yadadri.* | `targeted` | `False` | 1 | 6577.06 ms | ✅ PASSED |
| `11_BROAD_TEMPLE_INFO` | *Tell me everything about Dharmapuri Temple.* | `broad_temple` | `True` | 4 | 72935.21 ms | ✅ PASSED |
| `12_TARGETED_SINGLE_WHEELCHAIR` | *Does Dharmapuri have wheelchair facilities?* | `targeted` | `False` | 3 | 4142.33 ms | ✅ PASSED |
| `13_UNSUPPORTED_REFUSAL` | *Does Dharmapuri have a helicopter launch pad?* | `targeted` | `False` | 2 | 8637.27 ms | ✅ PASSED |

---

## 3. Query Details & Grounded Responses

### `1_TARGETED_SEVA_PRICE`
- **Query**: *"What is the price of Abhishekam in Dharmapuri?"*
- **Planned Mode**: `targeted` (Scope: `['Dharmapuri']`, Categories: `['sevas']`)
- **Latency**: `3804.08 ms`
- **Sources**: `['dharmapuri/faq.json', 'dharmapuri/prasadam.json', 'dharmapuri/sevas.json']`
- **Answer**:
> The price of Abhishekam in Dharmapuri is ₹500.

### `2_COMPLETE_SEVAS_DHARMAPURI`
- **Query**: *"What are all the sevas in Dharmapuri?"*
- **Planned Mode**: `complete_category` (Scope: `['Dharmapuri']`, Categories: `['sevas']`)
- **Latency**: `43878.21 ms`
- **Sources**: `['dharmapuri/sevas.json']`
- **Answer**:
> Based on the provided context, the sevas in Dharmapuri are:

1. Abhishekam
   - Telugu Name: అభిషేకం
   - Price: ₹500
   - Timing: from 6:00 AM
   - Description: Sri Swami vari Abh...

### `3_COMPLETE_FESTIVALS_BASARA`
- **Query**: *"List all festivals at Basara."*
- **Planned Mode**: `complete_category` (Scope: `['Basara']`, Categories: `['festivals']`)
- **Latency**: `19416.88 ms`
- **Sources**: `['basara/festivals.json']`
- **Answer**:
> Basara hosts the following festivals:

1. **Vasant Panchami / Sri Panchami** - Celebrated on Magha Masam, this festival features the highest annual single-day crowd density and is ...

### `4_AGGREGATION_RIVER_POSITIVE`
- **Query**: *"List all temples that have a river bank."*
- **Planned Mode**: `cross_temple_aggregation` (Scope: `[]`, Categories: `['river_bank']`)
- **Latency**: `10.54 ms`
- **Sources**: `['ahobilam/river_bank.json', 'badrachalam/river_bank.json', 'basara/river_bank.json', 'dharmapuri/river_bank.json', 'edupayal/river_bank.json', 'jogulamba(new)/river_bank.json', 'kaleshvaram/river_bank.json', 'medaram/river_bank.json', 'srisaila/river_bank.json', 'veera satyanarayana/river_bank.json', 'vemulavada/river_bank.json']`
- **Answer**:
> Based on the temple knowledge base, the following **11 temples** have confirmed **River Bank** information:

1. **Ahobilam** — River: Bhavanashini River (Pavanasini River) (Ghat: R...

### `5_AGGREGATION_WHEELCHAIR_NEGATIVE`
- **Query**: *"List all temples that don't have wheelchair facilities."*
- **Planned Mode**: `cross_temple_aggregation` (Scope: `[]`, Categories: `['wheelchair']`)
- **Latency**: `8.99 ms`
- **Sources**: `['balkampet/elderly_ppl.json', 'birla mandir/elderly_ppl.json', 'dharmapuri/elderly_ppl.json', 'edupayal/elderly_ppl.json', 'ramappa/elderly_ppl.json', 'thousand pillar/elderly_ppl.json', 'ujjaini/elderly_ppl.json']`
- **Answer**:
> Based on verified temple knowledge base records, the following **7 temples** are confirmed to **NOT have Wheelchair** (or have major documented architectural/physical limitations):...

### `6_AGGREGATION_ACCOMMODATION_POSITIVE`
- **Query**: *"Which temples have accommodation?"*
- **Planned Mode**: `cross_temple_aggregation` (Scope: `[]`, Categories: `['accommodation']`)
- **Latency**: `7.42 ms`
- **Sources**: `['ahobilam/accommodation.json', 'badrachalam/accommodation.json', 'balkampet/accommodation.json', 'basara/accommodation.json', 'birla mandir/accommodation.json', 'chilkur/accommodation.json', 'dharmapuri/accommodation.json', 'edupayal/accommodation.json', 'jogulamba(new)/accommodation.json', 'kaleshvaram/accommodation.json', 'karmanghat/accommodation.json', 'medaram/accommodation.json', 'ramappa/accommodation.json', 'srisaila/accommodation.json', 'thousand pillar/accommodation.json', 'ttd/accommodation.json', 'ujjaini/accommodation.json', 'veera satyanarayana/accommodation.json', 'vemulavada/accommodation.json', 'yadadri/accommodation.json']`
- **Answer**:
> Based on the temple knowledge base, the following **20 temples** have confirmed **Accommodation** information:

1. **Ahobilam** — Offers 4 accommodation options
2. **Badrachalam** ...

### `7_AGGREGATION_RESTAURANTS_NEGATIVE`
- **Query**: *"Which temples don't have restaurants?"*
- **Planned Mode**: `cross_temple_aggregation` (Scope: `[]`, Categories: `['restaurants']`)
- **Latency**: `6.3 ms`
- **Sources**: `[]`
- **Answer**:
> I could not find any temples with confirmed absence of restaurants in the available temple knowledge base.

### `8_MULTI_CATEGORY_ACCOMMODATION_RESTAURANTS`
- **Query**: *"What accommodation and restaurants are available near Dharmapuri?"*
- **Planned Mode**: `multi_category` (Scope: `['Dharmapuri']`, Categories: `['accommodation', 'restaurants']`)
- **Latency**: `7493.6 ms`
- **Sources**: `['dharmapuri/accommodation.json', 'dharmapuri/restaurants.json']`
- **Answer**:
> Accommodation:
- Sri Hanuman tiffins and meals (Type: Private Veg Hotel)
- New Geetha Bhavan (Type: Private Veg Hotel)

Restaurants:
- Sri Hanuman tiffins and meals (Type: Private ...

### `9_TARGETED_TIMINGS`
- **Query**: *"What are the timings of Dharmapuri Temple?"*
- **Planned Mode**: `targeted` (Scope: `['Dharmapuri']`, Categories: `['timings']`)
- **Latency**: `13010.94 ms`
- **Sources**: `['dharmapuri/faq.json', 'dharmapuri/restaurants.json', 'dharmapuri/timings.json']`
- **Answer**:
> The Dharmapuri Temple is open daily. Morning darshan timings are from 5:00 AM to 2:30 PM, and evening darshan timings are from 4:00 PM to 8:00 PM.

### `10_TARGETED_HISTORY`
- **Query**: *"Tell me the history of Yadadri."*
- **Planned Mode**: `targeted` (Scope: `['Yadadri']`, Categories: `['temple']`)
- **Latency**: `6577.06 ms`
- **Sources**: `['yadadri/temple.json']`
- **Answer**:
> The reconstruction of the Yadadri temple is one of the largest stone temple renovation projects in modern history. Executed by the Yadadri Temple Development Authority (YTDA) and d...

### `11_BROAD_TEMPLE_INFO`
- **Query**: *"Tell me everything about Dharmapuri Temple."*
- **Planned Mode**: `broad_temple` (Scope: `['Dharmapuri']`, Categories: `[]`)
- **Latency**: `72935.21 ms`
- **Sources**: `['dharmapuri/festivals.json', 'dharmapuri/prasadam.json', 'dharmapuri/restaurants.json', 'dharmapuri/sevas.json']`
- **Answer**:
> Dharmapuri Temple is a comprehensive temple located in Dharmapuri, Telangana. It offers a variety of services and events throughout the year, including Sevas, festivals, and restau...

### `12_TARGETED_SINGLE_WHEELCHAIR`
- **Query**: *"Does Dharmapuri have wheelchair facilities?"*
- **Planned Mode**: `targeted` (Scope: `['Dharmapuri']`, Categories: `['wheelchair']`)
- **Latency**: `4142.33 ms`
- **Sources**: `['dharmapuri/elderly_ppl.json', 'dharmapuri/emergency_nos.json', 'dharmapuri/facilities.json']`
- **Answer**:
> No, Dharmapuri does not have wheelchair facilities.

### `13_UNSUPPORTED_REFUSAL`
- **Query**: *"Does Dharmapuri have a helicopter launch pad?"*
- **Planned Mode**: `targeted` (Scope: `['Dharmapuri']`, Categories: `[]`)
- **Latency**: `8637.27 ms`
- **Sources**: `['dharmapuri/faq.json', 'dharmapuri/rules.json']`
- **Answer**:
> No, Dharmapuri does not have a helicopter launch pad.

