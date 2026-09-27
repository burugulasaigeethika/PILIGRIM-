# Phase 7 Answer Grounding & Scope Control Evaluation Report

## 1. Executive Summary
- **Evaluation Date**: 2026-08-25 23:18:01
- **Total Test Queries Evaluated**: 11
- **Passed Scope Tests**: 11 / 11 (100.0%)
- **Unrelated Information Rate for Targeted Queries**: **0.0%** (Target: 0.0%)
- **Local Environment**: 100% Local / Offline (Qwen 2.5:1.5B via Ollama)

---

## 2. Benchmark Query Scope & Grounding Results

| Test ID | Query | Retrieval Mode | Scope Temples | Scope Categories | Unrelated Info Violations | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `BHADRACHALAM_TIMINGS_TARGETED` | *What are the temple timings at Bhadrachalam?* | `targeted` | `['Badrachalam']` | `['timings']` | 0 | ✅ PASSED |
| `DHARMAPURI_ABHISHEKAM_PRICE_TARGETED` | *What is the price of Abhishekam in Dharmapuri?* | `targeted` | `['Dharmapuri']` | `['sevas']` | 0 | ✅ PASSED |
| `DHARMAPURI_ALL_SEVAS_COMPLETE` | *What are all the sevas in Dharmapuri?* | `complete_category` | `['Dharmapuri']` | `['sevas']` | 0 | ✅ PASSED |
| `BASARA_ALL_FESTIVALS_COMPLETE` | *List all festivals at Basara.* | `complete_category` | `['Basara']` | `['festivals']` | 0 | ✅ PASSED |
| `RIVER_BANK_AGGREGATION` | *List all temples that have a river bank.* | `cross_temple_aggregation` | `['*']` | `['river_bank']` | 0 | ✅ PASSED |
| `WHEELCHAIR_NEGATIVE_AGGREGATION` | *List all temples that don't have wheelchair facilities.* | `cross_temple_aggregation` | `['*']` | `['wheelchair']` | 0 | ✅ PASSED |
| `MULTI_CATEGORY_ACCOMMODATION_RESTAURANTS` | *What accommodation and restaurants are available near Dharmapuri?* | `multi_category` | `['Dharmapuri']` | `['accommodation', 'restaurants']` | 0 | ✅ PASSED |
| `YADADRI_HISTORY_TARGETED` | *Tell me the history of Yadadri.* | `targeted` | `['Yadadri']` | `['temple']` | 0 | ✅ PASSED |
| `DHARMAPURI_BROAD_OVERVIEW` | *Tell me everything about Dharmapuri Temple.* | `broad_temple` | `['Dharmapuri']` | `['*']` | 0 | ✅ PASSED |
| `DHARMAPURI_WHEELCHAIR_TARGETED` | *Does Dharmapuri have wheelchair facilities?* | `targeted` | `['Dharmapuri']` | `['wheelchair']` | 0 | ✅ PASSED |
| `HELIPAD_GROUNDED_REFUSAL` | *Does Dharmapuri have a helicopter launch pad?* | `targeted` | `['Dharmapuri']` | `['*']` | 0 | ✅ PASSED |

---

## 3. Detailed Query Responses

### `BHADRACHALAM_TIMINGS_TARGETED`
- **Query**: *"What are the temple timings at Bhadrachalam?"*
- **Planned Mode**: `targeted` | Scope Temples: `['Badrachalam']` | Categories: `['timings']`
- **Latency**: `16907.35 ms`
- **Answer Output**:
> The temple is open daily from 4:30 AM to 1:00 PM and from 3:00 PM to 9:00 PM. The temple is closed for afternoon rest between 1:00 PM and 3:00 PM.

### `DHARMAPURI_ABHISHEKAM_PRICE_TARGETED`
- **Query**: *"What is the price of Abhishekam in Dharmapuri?"*
- **Planned Mode**: `targeted` | Scope Temples: `['Dharmapuri']` | Categories: `['sevas']`
- **Latency**: `14273.76 ms`
- **Answer Output**:
> ₹500

### `DHARMAPURI_ALL_SEVAS_COMPLETE`
- **Query**: *"What are all the sevas in Dharmapuri?"*
- **Planned Mode**: `complete_category` | Scope Temples: `['Dharmapuri']` | Categories: `['sevas']`
- **Latency**: `19380.22 ms`
- **Answer Output**:
> Here is a complete list of all the sevas in Dharmapuri:

1. Abhishekam
2. Tulasi Visheṣārchana
3. Sahasranamas / Korika Nivṛtti
4. Gokṣanāma Harati
5. Odi Biyyam
6. Kumkuma Archana
7. Pulihora Bhogam / Dadhojana Bhogam
8. Bōrela Bhogam
9. Veda Aashirvachanam
10. Mudupu

### `BASARA_ALL_FESTIVALS_COMPLETE`
- **Query**: *"List all festivals at Basara."*
- **Planned Mode**: `complete_category` | Scope Temples: `['Basara']` | Categories: `['festivals']`
- **Latency**: `43756.14 ms`
- **Answer Output**:
> Basara hosts a variety of festivals throughout the year, each with its own unique significance and celebration. Here is a complete list of festivals celebrated at Basara:

1. **Vasant Panchami / Sri Panchami**
   - Description: The grandest festival celebrated at Sri Gnana Saraswathi Temple, Basara. Lakhs of devotees and parents visit the temple to perform Akshara Abhyasam (holy initiation into learning and education) for children.
   - Month: Magha Masam (Typically matches January or February)
   - Importance: Widely revered as the manifestation day (Saraswathi Jayanthi) of the Goddess of Knowledge. It features the absolute highest annual single-day crowd density.

2. **Devi Navarathrotsavams (Sharad Navratri)**
   - Description: 9-day grand celebrations dedicated to Goddess Durga, Lakshmi, and Saraswathi with special Alankarams, Chandi Homam, and religious discourses.
   - Month: Ashwayuja Masam (Typically matches September or October)
   - Importance: Marks the victory of light over spiritual darkness. Celebrates high-density Vedic chanting sessions and elaborate ritual decoration shifts across the main shrine layouts.

3. **Mahasivarathri Jathra**
   - Description: Major festival where lakhs of pilgrims visit the shrine to offer vows to Lord Vyaseshwara & Lord Shiva on the banks of Godavari.
   - Month: Magha Masam / Bahula Trayodashi (Typically matches February or March)
   - Importance: Highlights the deep historical intersection of Saivite and Vaishnavite traditions at Basara, drawing extensive night-long meditation crowds to the river banks.

4. **Vyasa Pournima**
   - Description: Vyasa paurnima Utsavam is celebrated on Ashada Paurnima. As the legend of the temple says the Deity of the temple was established by Veda Vyasa, hence Utasavam is performed in a large scale.
   - For more details about the Vyasa Paurnima Utsavam at Basara Temple contact Basara Devasthanam.
   - Month: Ashadha Masam (Typically matches June or July)
   - Importance: A deeply unique heritage festival specific to Basara. Celebrated on a massive scale to pay ancestral homage to the legendary author of the Mahabharata and the Puranas.

5. **Other Festivals**
   - Sreerama Navami
   - Vyasa Purnima
   - Sravana Masotsavam
   - Kartheeka Masotsavam
   - Deepavali
   - Akshaya Tritiya
   - Month: Distributed across the Hindu Lunar Calendar cycles
   - Importance: Ensures the continuous flow of seasonal community prayers, special evening oil-lamp line lightings (Deepotsavam), and localized multi-deity offerings.

### `RIVER_BANK_AGGREGATION`
- **Query**: *"List all temples that have a river bank."*
- **Planned Mode**: `cross_temple_aggregation` | Scope Temples: `['*']` | Categories: `['river_bank']`
- **Latency**: `9.57 ms`
- **Answer Output**:
> Based on the temple knowledge base, the following **11 temples** have confirmed **River Bank** information:

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

### `WHEELCHAIR_NEGATIVE_AGGREGATION`
- **Query**: *"List all temples that don't have wheelchair facilities."*
- **Planned Mode**: `cross_temple_aggregation` | Scope Temples: `['*']` | Categories: `['wheelchair']`
- **Latency**: `8.9 ms`
- **Answer Output**:
> Based on verified temple knowledge base records, the following **7 temples** are confirmed to **NOT have Wheelchair** (or have major documented architectural/physical limitations):

1. **Balkampet** — Not wheelchair friendly (Subterranean Staircase Access Only: The main self-manifested sanctum is situated 10 feet below groun)
2. **Birla Mandir** — Not wheelchair friendly (Lift Available with Step Caveats: An on-site elevator/lift facility is operated for senior citizens )
3. **Dharmapuri** — Not wheelchair friendly (Walking Aids Recommended: Navigating the stone temple courtyards (Prakarams) and long flight of ston)
4. **Edupayal** — Not wheelchair friendly (Riverbed Cave Shrine Access: The self-manifested sanctum is located directly within the riverbed of )
5. **Ramappa** — Not wheelchair friendly (Not Wheelchair Friendly: The temple is built on a high, star-shaped raised platform typical of Kakat)
6. **Thousand Pillar** — Not wheelchair friendly (Accessible Entrance Gates: The main entrance and exit pathways are wide and flat, allowing convenien)
7. **Ujjaini** — Not wheelchair friendly (The temple is a historic structure located in a dense urban market area. It currently lacks dedicate)

*(Note: 7 temples have no specific wheelchair records documented in the current knowledge base).*

### `MULTI_CATEGORY_ACCOMMODATION_RESTAURANTS`
- **Query**: *"What accommodation and restaurants are available near Dharmapuri?"*
- **Planned Mode**: `multi_category` | Scope Temples: `['Dharmapuri']` | Categories: `['accommodation', 'restaurants']`
- **Latency**: `30727.9 ms`
- **Answer Output**:
> ### Accommodation
- **Name:** Sri Hanuman tiffins and meals
  - **Cuisine:** Authentic South Indian vegetarian meals, breakfast tiffins (idli, dosa, vada), and simple rice items
  - **Type:** Private Veg Hotel
  - **Distance:** ~ 900 m
  - **Pricing:** Affordable / Budget-friendly
  - **Timings:** Monday to Sunday, 6:00 AM – 11:30 PM
  - **Address:** Sri Laxmi Narasimha, 3-57, Swami Temple Road, near Laxmi Narasimha Swamy Temple, Boyawada, Police Quarters, Dharmapuri, Telangana 505425

- **Name:** New Geetha Bhavan
  - **Cuisine:** Pure vegetarian South Indian breakfast specialties and standard afternoon lunch plates
  - **Type:** Private Veg Hotel
  - **Distance:** Approximately 350 meters away from the temple area
  - **Pricing:** Affordable / Budget-friendly
  - **Timings:** Monday to Sunday, 8:00 AM – 8:00 PM
  - **Address:** Guest House Road, Boyawada, Dharmapuri, Jagtial - 505425 (Opposite Vani Vidhyalayam)

### Restaurants
- **Name:** Temple Nithya Annadanam
  - **Cuisine:** Traditional vegetarian temple meal
  - **Type:** Temple Annadanam
  - **Distance:** Within the Sri Lakshmi Narasimha Swamy Temple complex
  - **Pricing:** Free
  - **Timings:** Daily Annadanam is available; exact serving hours should be confirmed with the temple
  - **Address:** Sri Lakshmi Narasimha Swamy Temple Complex, Dharmapuri, Telangana 505425

### `YADADRI_HISTORY_TARGETED`
- **Query**: *"Tell me the history of Yadadri."*
- **Planned Mode**: `targeted` | Scope Temples: `['Yadadri']` | Categories: `['temple']`
- **Latency**: `26041.27 ms`
- **Answer Output**:
> The reconstruction of the Yadadri temple is one of the largest stone temple renovation projects in modern history. Executed by the Yadadri Temple Development Authority (YTDA) and designed by chief architect Anand Sai and traditional sthapatis, the temple has been expanded from a 2-acre hill shrine to a sprawling 17-acre stone complex. The temple is celebrated as a major spiritual center of Sanatana Dharma, located in the Yadadri Bhuvanagiri district of Telangana. The Five Manifestations (Swayambhu Cave Deities) include Jwala Narasimha, Yogananda Narasimha, Gandabherunda Narasimha, Ugra Narasimha, and Lakshmi Narasimha. The temple's architectural marvel is the Krishna Shila, built entirely out of black granite sourced from Guntur and Prakasam districts, and features seven gopurams.

### `DHARMAPURI_BROAD_OVERVIEW`
- **Query**: *"Tell me everything about Dharmapuri Temple."*
- **Planned Mode**: `broad_temple` | Scope Temples: `['Dharmapuri']` | Categories: `['*']`
- **Latency**: `72901.72 ms`
- **Answer Output**:
> Dharmapuri Temple, also known as Sri Lakshmi Narasimha Swamy Temple, is a significant religious site located in Dharmapuri, Telangana. The temple is known for its rich history, diverse offerings, and annual festivals. The temple is situated near the Sri Laxmi Narasimha Swamy Temple, making it a popular destination for pilgrims and devotees.

The temple is known for its Sevas, which are religious rituals performed by the temple priests. The Sevas include Abhishekam, Tulasi Visheṣārchana, Sahasranamas / Korika Nivṛtti, Gokṣanāma Harati, Odi Biyyam, Kumkuma Archana, Pulihora Bhogam / Dadhojana Bhogam, and Bōrela Bhogam. These Sevas are performed daily during the temple's Archana slots, with specific timings and descriptions provided.

The temple is also known for its festivals, which are celebrated annually. The festivals include the Abhisheka Festival, which is held on the first day of the Hindu month of Chaitra, and the Nityanivedana Festival, which is held on the last day of the month. The festivals are marked by elaborate rituals and offerings, and the temple is adorned with colorful decorations and lights.

The temple is also known for its restaurants, which offer a variety of vegetarian meals. The restaurants include Sri Hanuman tiffins and meals, New Geetha Bhavan, and Temple Nithya Annadanam. These restaurants provide affordable and budget-friendly meals, with specific timings and locations provided.

The temple is also known for its Prasadam, which is distributed following the Sevas and during the evening Aaradhana & Pavalimpu Seva. The Prasadam includes Abhishekam Prasadam, Pulihora Bhogam, Dadhojana Bhogam, and Bōrela Bhogam, with specific timings and locations provided.

The temple is also known for its Prasadam, which is distributed following the Sevas and during the evening Aaradhana & Pavalimpu Seva. The Prasadam includes Abhishekam Prasadam, Pulihora Bhogam, Dadhojana Bhogam, and Bōrela Bhogam, with specific timings and locations provided.

The temple is also known for its Prasadam, which is distributed following the Sevas and during the evening Aaradhana & Pavalimpu Seva. The Prasadam includes Abhishekam Prasadam, Pulihora Bhogam, Dadhojana Bhogam, and Bōrela Bhogam, with specific timings and locations provided.

The temple is also known for its Prasadam, which is distributed following the Sevas and during the evening Aaradhana & Pavalimpu Seva. The Prasadam includes Abhishekam Prasadam, Pulihora Bhogam, Dadhojana Bhogam, and Bōrela Bhogam, with specific timings and locations provided.

The temple is also known for its Prasadam, which is distributed following the Sevas and during the evening Aaradhana & Pavalimpu Seva. The Prasadam includes Abhishekam Prasadam, Pulihora Bhogam, Dadhojana Bhogam, and Bōrela Bhogam, with specific timings and locations provided.

The temple is also known for its Prasadam, which is distributed following the Sevas and during the evening Aaradhana & Pavalimpu Seva. The Pras

### `DHARMAPURI_WHEELCHAIR_TARGETED`
- **Query**: *"Does Dharmapuri have wheelchair facilities?"*
- **Planned Mode**: `targeted` | Scope Temples: `['Dharmapuri']` | Categories: `['wheelchair']`
- **Latency**: `19619.21 ms`
- **Answer Output**:
> No

### `HELIPAD_GROUNDED_REFUSAL`
- **Query**: *"Does Dharmapuri have a helicopter launch pad?"*
- **Planned Mode**: `targeted` | Scope Temples: `['Dharmapuri']` | Categories: `['*']`
- **Latency**: `12313.26 ms`
- **Answer Output**:
> I could not find this information in the temple knowledge base.

