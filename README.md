# 🌟 AI-Powered Lead Qualification Engine  
### Python • Streamlit • Selenium • Pandas • Groq API

An intelligent Streamlit-based system that scrapes game-development job listings from Hitmarker and evaluates each lead using an AI-assisted ICP (Ideal Customer Profile) scoring engine.  

The app allows users to enter a **keyword**, choose whether to scrape a **single page or all pages**, and then automatically processes the scraped jobs through an AI-powered qualification pipeline.

---

## 📌 Short Description
**An AI-powered lead qualification system that scrapes Hitmarker job listings, enriches each role using configurable rules, and generates ICP scores based on service relevance, industry alignment, region, company size, and revenue.**

---

# 📸 Screenshots (Placeholders)

### **Dashboard Home**
<img width="1824" height="993" alt="image" src="https://github.com/user-attachments/assets/f68ce1bc-d40b-4d7e-8331-41dec27c9e56" />


### **Scraping in Progress**
<img width="1828" height="982" alt="image" src="https://github.com/user-attachments/assets/0646dc42-f8b7-42c2-9d14-4bfb031b1188" />


### **Final Output**
> _Place an image here_  
<img width="1840" height="1020" alt="Screenshot 2025-11-20 112510" src="https://github.com/user-attachments/assets/cdf2ee79-74c3-4f72-89c4-e0ed28a2cbfd" />
<img width="1727" height="723" alt="Screenshot 2025-11-20 112447" src="https://github.com/user-attachments/assets/c9fde122-3279-4995-abe2-867674f78480" />
<img width="1720" height="685" alt="Screenshot 2025-11-20 112456" src="https://github.com/user-attachments/assets/71d26645-1262-48a8-9c0b-a123f16eb523" />

<img width="1920" height="1029" alt="image" src="https://github.com/user-attachments/assets/5f7d47c9-44d2-4e8a-be9d-44091b4e650f" />

---

# 🚀 Features

### 🔍 **1. Keyword-based Web Scraping (Hitmarker)**
- Enter any job keyword (e.g., *“unreal”, “3d artist”, “unity developer”*)
- Choose:
  - **Scrape Single Page**
  - **Scrape All Pages**
- Selenium with undetected-chromedriver
- Image-blocking mode for performance
- Clean extraction of:
  - Job Title  
  - Company  
  - Location  
  - URL  

---

### 🤖 **2. AI-Driven Qualification Engine**
Runs automatically on scraped jobs.

Performs:

- **Service Classification**  
  (Maps titles into Art, Co-Dev, Full, None)
- **Industry Detection**  
  (Gaming vs Non-gaming)
- **Company Stats Estimation**  
  - HQ region  
  - Employee range  
  - Revenue tier  
- **ICP Score Calculation**  
  Weighted scoring across:
  - Region  
  - Service relevance  
  - Revenue  
  - Employee size  
  - Industry match  

---

### 📊 **3. Streamlit Dashboard**
User-friendly UI:

- Keyword input  
- “Scrape All Pages” toggle  
- Real-time scraping logs  
- Interactive Data Table  
- Download as:
  - `.xlsx`

---

### 💾 **4. Automatic Caching Layer**
All expensive operations are cached:

| Cache File | Purpose |
|------------|---------|
| `classify_cache.json` | Title → service bucket |
| `company_cache.json` | Company stats |
| `industry_cache.json` | Industry classification |
| `trusted_stats.json` | Pre-loaded for known game studios |

Speeds up re-runs dramatically.

---

# 🏗 Folder Structure

<img width="333" height="524" alt="image" src="https://github.com/user-attachments/assets/9115478f-01db-4c99-8b63-4824f86cd23b" />

---

# ⚙️ Installation

### **1. Create environment**
python -m venv venv
venv/Scripts/activate

### **2. Install the required Packages**
pip install -r requirements.txt

### **3. Add environment variable**
create .env in root:
GROQ_API_KEY=your_key_here

---
▶️ Usage
**Start the Streamlit App:**
streamlit run dashboard.py

**Workflow inside UI**
1.Enter a keyword → “unreal”, “3d artist”, “unity developer”, etc

2.Choose:
Scrape single page
Or Scrape all pages

3.Hit SCRAPE

4.Data is scraped via Selenium

5.AI qualification engine runs automatically

6.Final results (with ICP score) shown on screen

7.Download Excel/CSV
---

📊 ICP Scoring Model
Five weighted components
| Component      | Weight |
| -------------- | ------ |
| Employee Range | 25%    |
| Revenue Range  | 25%    |
| Region Match   | 20%    |
| Service Bucket | 15%    |
| Industry Match | 15%    |

---
**Qualification Decision**
A company is Qualified if:
Legacy rule set passes
OR Weighted ICP ≥ threshold (default = 75)

---
🔧 Configuration Files
| File                    | Use                        |
| ----------------------- | -------------------------- |
| `service_mapping.json`  | Maps job titles → services |
| `region_mapping.json`   | Normalizes region names    |
| `revenue_mapping.json`  | Allowed revenue tiers      |
| `industry_mapping.json` | Gaming & non-gaming lists  |
| `icp_rules.json`        | Score weights & thresholds |

You can freely modify these files to adapt scoring logic.


**Architecture Diagram**

<img width="2400" height="882" alt="Untitled diagram-2025-11-20-062727" src="https://github.com/user-attachments/assets/729b499d-755c-4c9d-8434-13fdc73af1f3" />

---
🛣 **Roadmap**
1.Add LinkedIn integration
2.Add Indeed integration
---

📜 **License**
This project is licensed under the MIT License.
See the LICENSE file for details.
---
👤 **Author**
Created by Shashank Kamath
For academic + industry use.
