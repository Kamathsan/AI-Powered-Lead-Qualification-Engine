# qualifier_engine.py
"""
Fully modular qualifier engine (Option 1).
- Loads rule mappings from config/*.json
- Backwards compatible with previous functions (run_qualification, process_dataframe, run_icp_engine_logic)
- Safe fallbacks if Groq/LLM or config files are missing
- Keeps original scoring/legacy logic
"""

import os
import json
import time
import re
import random
import traceback
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import pandas as pd

# -------------------------
# Files / constants
# -------------------------
ROOT = Path(__file__).parent
CONFIG_DIR = ROOT / "config"
CONFIG_DIR.mkdir(exist_ok=True)

INPUT_FILE = "Book1.xlsx"
OUTPUT_XLSX = "qualified_leads_final.xlsx"
PARTIAL_CSV = "qualified_leads_partial.csv"
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
COMPANY_CACHE_FILE = CACHE_DIR / "company_cache.json"
INDUSTRY_CACHE_FILE = CACHE_DIR / "industry_cache.json"
CLASSIFY_CACHE_FILE = CACHE_DIR / "classify_cache.json"
CHECKPOINT_FILE = CACHE_DIR / "progress_checkpoint.json"
TRUSTED_STATS_FILE = CACHE_DIR / "trusted_stats.json"

SAVE_EVERY_N = 50

# default weights (kept same as you used)
WEIGHTS = {
    "employees": 25,
    "revenue": 25,
    "region": 20,
    "service": 15,
    "industry": 15
}
SCORE_THRESHOLD = 75

# -------------------------
# Load env + optional Groq client
# -------------------------
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
try:
    if API_KEY:
        from groq import Groq
        client = Groq(api_key=API_KEY)
    else:
        client = None
except Exception:
    client = None

# -------------------------
# Helper: load/save json
# -------------------------
def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_json(path: Path, obj: dict):
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

company_cache: Dict[str, Dict[str, str]] = load_json(COMPANY_CACHE_FILE)
industry_cache: Dict[str, bool] = load_json(INDUSTRY_CACHE_FILE)
classify_cache: Dict[str, Dict[str, str]] = load_json(CLASSIFY_CACHE_FILE)

# -------------------------
# Config loader (modular)
# -------------------------
def _load_config(name: str, default: dict) -> dict:
    p = CONFIG_DIR / f"{name}.json"
    if not p.exists():
        # write the default so user can tweak later
        save_json(p, default)
        return default
    try:
        return load_json(p)
    except Exception:
        return default

# Minimal sane defaults (these will be written to config/*.json if missing)
DEFAULT_SERVICE_MAPPING = {
    # key -> detailed_service, service_bucket
    "animation": ["Animation", "Art"],
    "animator": ["Animation", "Art"],
    "vfx": ["VFX", "Art"],
    "technical artist": ["Technical Art", "Art"],
    "technical animator": ["Technical Animation", "Art"],
    "engineer": ["Programming", "Co-Dev"],
    "programmer": ["Programming", "Co-Dev"],
    "engine programmer": ["Programming", "Co-Dev"],
    "tools": ["Programming Tools", "Co-Dev"],
    "producer": ["Game Production", "Full"],
    "level designer": ["Game Production", "Full"],
    "design": ["Game Development", "Full"],
    "ui": ["UI/UX", "Art"],
    "ux": ["UI/UX", "Art"],
    "render": ["Rendering", "Co-Dev"],
    "rig": ["Rigging", "Art"]
}
DEFAULT_REGION_MAPPING = {
    # canonical lowercase -> list of terms to match
    "united states": ["united states", "usa", "us"],
    "canada": ["canada"],
    "france": ["france"],
    "uk": ["uk", "united kingdom", "great britain", "england"],
    "germany": ["germany"],
    "japan": ["japan"],
    "china": ["china"],
    "finland": ["finland"],
    "sweden": ["sweden"],
    "poland": ["poland"],
    "australia": ["australia"],
    "singapore": ["singapore"],
    "india": ["india"]
}
DEFAULT_INDUSTRY_MAPPING = {
    "trusted_game_companies": [
        "ubisoft","epic games","riot games","cd projekt red","bethesda","activision","blizzard",
        "respawn","naughty dog","take-two","square enix","nintendo","playstation","scopely",
        "keywords studios","gameloft","supercell","behaviour interactive","dices","insomniac",
        "rockstar","ea","sony","konami","remedy"
    ],
    "forced_non_gaming": ["linkedin","tcs","infosys","deloitte","bosch","walmart","cognizant","accenture","capgemini","hcl"]
}
DEFAULT_REVENUE_MAPPING = {
    # keep only labels used in scoring
    "ranges": ["<5M","5M-50M","50M-500M","500M-1B",">1B"]
}
DEFAULT_ICP_RULES = {
    "good_regions": list(DEFAULT_REGION_MAPPING.keys()),
    "weights": WEIGHTS,
    "score_threshold": SCORE_THRESHOLD
}

# load configs (files will be created if missing)
SERVICE_MAPPING = _load_config("service_mapping", DEFAULT_SERVICE_MAPPING)
REGION_MAPPING = _load_config("region_mapping", DEFAULT_REGION_MAPPING)
INDUSTRY_MAPPING = _load_config("industry_mapping", DEFAULT_INDUSTRY_MAPPING)
REVENUE_MAPPING = _load_config("revenue_mapping", DEFAULT_REVENUE_MAPPING)
ICP_RULES = _load_config("icp_rules", DEFAULT_ICP_RULES)

GOOD_REGIONS = [r.lower() for r in ICP_RULES.get("good_regions", list(DEFAULT_REGION_MAPPING.keys()))]
WEIGHTS = ICP_RULES.get("weights", WEIGHTS)
SCORE_THRESHOLD = ICP_RULES.get("score_threshold", SCORE_THRESHOLD)

# -------------------------
# Trusted stats default (saved to cache once)
# -------------------------
if not TRUSTED_STATS_FILE.exists():
    TRUSTED_STATS = {
        "epic games": {"hq_country": "United States", "employees": ">20000", "revenue": ">1B"},
        "ubisoft": {"hq_country": "France", "employees": ">20000", "revenue": ">1B"},
        "riot games": {"hq_country": "United States", "employees": "5000-20000", "revenue": ">1B"},
        "ea": {"hq_country": "United States", "employees": ">20000", "revenue": ">1B"},
        "cd projekt red": {"hq_country": "Poland", "employees": "5000-20000", "revenue": "500M-1B"},
    }
    save_json(TRUSTED_STATS_FILE, TRUSTED_STATS)
else:
    TRUSTED_STATS = load_json(TRUSTED_STATS_FILE)

# -------------------------
# JSON repair helper
# -------------------------
def repair_json(text: Optional[str]):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    fixed = (text.replace("'", '"').replace("\n", " ").replace(",}", "}").replace(", ]", "]").strip())
    try:
        return json.loads(fixed)
    except Exception:
        return None

# -------------------------
# Groq / LLM safe wrapper
# -------------------------
RATE_LOCK = threading.Lock()
CALLS_IN_WINDOW = 0
WINDOW_START = time.time()
WINDOW_SEC = 60
RPM_LIMIT = 28

def rate_limited_groq(prompt: str, max_tokens: int = 200):
    global CALLS_IN_WINDOW, WINDOW_START, client
    if client is None:
        return None
    for attempt in range(4):
        with RATE_LOCK:
            now = time.time()
            if now - WINDOW_START >= WINDOW_SEC:
                CALLS_IN_WINDOW = 0
                WINDOW_START = now
            if CALLS_IN_WINDOW >= RPM_LIMIT:
                sleep_for = WINDOW_SEC - (now - WINDOW_START) + 0.1
                print(f"Rate limit reached. Sleeping {sleep_for:.1f}s")
                time.sleep(sleep_for)
                CALLS_IN_WINDOW = 0
                WINDOW_START = time.time()
            CALLS_IN_WINDOW += 1
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"Groq error attempt {attempt+1}: {e}")
            time.sleep(1.5 * (attempt + 1))
    return None

# -------------------------
# Normalizers + rules (modular)
# -------------------------
def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"\b(senior|sr|lead|principal|ii|iii|iv|jr|junior|mid|intern|internship)\b", "", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def is_game_role(title: str) -> bool:
    t = normalize_title(title)
    keywords = [
        "game","unreal","unity","gameplay","designer","producer","3d","2d","artist",
        "ui","ux","vfx","fx","animator","render","graphics","engine","engineer",
        "tools","rig","rigging","technical art","lighting","animation","pipeline",
        "concept","level","narrative","technical animator","technical artist"
    ]
    return any(k in t for k in keywords)

def classify_service_rule(title: str) -> Optional[Dict[str,str]]:
    t = normalize_title(title)
    # check mapping keys (longest first)
    for key in sorted(SERVICE_MAPPING.keys(), key=lambda x: -len(x)):
        if key in t:
            val = SERVICE_MAPPING[key]
            # allow either ["Detailed","Bucket"] or {"detailed":..., "bucket":...}
            if isinstance(val, list) and len(val) >= 2:
                return {"detailed_service": val[0], "service_bucket": val[1]}
            if isinstance(val, dict):
                return {"detailed_service": val.get("detailed_service","Unknown"), "service_bucket": val.get("service_bucket","None")}
    return None

# -------------------------
# Caching wrappers (same behavior)
# -------------------------
def classify_service(title: str) -> Dict[str, str]:
    key = normalize_title(title)
    if key in classify_cache:
        return classify_cache[key]
    rule = classify_service_rule(title)
    if rule:
        classify_cache[key] = rule
        save_json(CLASSIFY_CACHE_FILE, classify_cache)
        return rule
    # fallback LLM if available
    prompt = f"""
Classify the job title into a JSON with keys:
"detailed_service" and "service_bucket" (Art / Co-Dev / Full / None).
Job Title: "{title}"
"""
    out = rate_limited_groq(prompt, max_tokens=150)
    parsed = repair_json(out)
    if parsed and "detailed_service" in parsed and "service_bucket" in parsed:
        classify_cache[key] = parsed
    else:
        classify_cache[key] = {"detailed_service": "Unknown", "service_bucket": "None"}
    save_json(CLASSIFY_CACHE_FILE, classify_cache)
    return classify_cache[key]

def get_company_info(company: str) -> Dict[str,str]:
    key = company.lower().strip()
    if key in TRUSTED_STATS:
        return TRUSTED_STATS[key]
    if key in company_cache:
        return company_cache[key]
    prompt = f"""
Estimate HQ country, employee range, and revenue range for the company.
Employees must be one of: <10, 10-50, 50-500, 500-5000, 5000-20000, >20000
Revenue must be one of: <5M, 5M-50M, 50M-500M, 500M-1B, >1B
Return STRICT JSON with keys: hq_country, employees, revenue
Company: "{company}"
"""
    out = rate_limited_groq(prompt, max_tokens=180)
    parsed = repair_json(out)
    if parsed and "hq_country" in parsed and "employees" in parsed and "revenue" in parsed:
        company_cache[key] = parsed
    else:
        company_cache[key] = {"hq_country": "Unknown", "employees": "Unknown", "revenue": "Unknown"}
    save_json(COMPANY_CACHE_FILE, company_cache)
    return company_cache[key]

def detect_industry(company: str, title: str) -> bool:
    key = f"{company.lower().strip()}||{normalize_title(title)}"
    if key in industry_cache:
        return industry_cache[key]

    company_lower = company.lower().strip()

    forced_non = INDUSTRY_MAPPING.get("forced_non_gaming", [])
    if company_lower in forced_non:
        industry_cache[key] = False
        save_json(INDUSTRY_CACHE_FILE, industry_cache)
        return False

    trusted = set(INDUSTRY_MAPPING.get("trusted_game_companies", []))
    if any(name in company_lower for name in trusted):
        industry_cache[key] = True
        save_json(INDUSTRY_CACHE_FILE, industry_cache)
        return True

    # name heuristics
    if any(k in company_lower for k in ["games","studio","interactive","entertainment","gamedev","game","play","mobile"]):
        industry_cache[key] = True
        save_json(INDUSTRY_CACHE_FILE, industry_cache)
        return True

    # fallback LLM question (cheap)
    prompt = f"Does the company '{company}' operate in game development / publishing or interactive entertainment? Answer YES or NO."
    out = rate_limited_groq(prompt, max_tokens=12)
    if out and "yes" in out.lower():
        industry_cache[key] = True
    else:
        industry_cache[key] = False
    save_json(INDUSTRY_CACHE_FILE, industry_cache)
    return industry_cache[key]

# -------------------------
# Scoring functions (kept same)
# -------------------------
def score_employees(emp_range: str) -> int:
    if emp_range in ["50-500","500-5000"]:
        return 60
    if emp_range in ["5000-20000", ">20000"]:
        return 100
    return 0

def score_revenue(rev_range: str) -> int:
    if rev_range in ["50M-500M"]:
        return 60
    if rev_range in ["500M-1B", ">1B"]:
        return 100
    return 0

def score_region(hq_country: str) -> int:
    if not hq_country:
        return 0
    lower = hq_country.lower()
    if any(r in lower for r in GOOD_REGIONS):
        return 100
    return 0

def score_service(bucket: str) -> int:
    if bucket in ("Art","Co-Dev","Full"):
        return 100
    return 0

def score_industry(ind_ok: bool) -> int:
    return 100 if ind_ok else 0

def weighted_score(emp, rev, hq, bucket, industry_ok) -> float:
    e = score_employees(emp)
    r = score_revenue(rev)
    reg = score_region(hq)
    s = score_service(bucket)
    i = score_industry(industry_ok)
    total = (e * WEIGHTS["employees"] + r * WEIGHTS["revenue"] + reg * WEIGHTS["region"] + s * WEIGHTS["service"] + i * WEIGHTS["industry"]) / 100.0
    return round(total, 2)

def legacy_qualify(company, bucket, detailed, hq, emp, rev, industry_pass):
    reasons = []
    pass_flag = True
    if emp in ["50-500","500-5000","5000-20000",">20000"]:
        reasons.append("employee size ok")
    else:
        reasons.append("employee size too small")
        pass_flag = False
    if rev in ["50M-500M","500M-1B",">1B"]:
        reasons.append("revenue ok")
    else:
        reasons.append("revenue too low")
        pass_flag = False
    if any(r in (hq or "").lower() for r in GOOD_REGIONS):
        reasons.append("region ok")
    else:
        reasons.append("region outside ICP")
        pass_flag = False
    if bucket != "None":
        reasons.append("service relevant")
    else:
        reasons.append("service mismatch")
        pass_flag = False
    if industry_pass:
        reasons.append("gaming industry match")
    else:
        reasons.append("not gaming industry")
        pass_flag = False
    if pass_flag:
        return {"decision":"Qualified","reason":f"{company} matches ICP ({', '.join(reasons)}).","confidence":"95%"}
    return {"decision":"Not Qualified","reason":", ".join(reasons),"confidence":"75%"}

def decide(company, bucket, detailed, hq, emp, rev, industry_pass):
    legacy = legacy_qualify(company, bucket, detailed, hq, emp, rev, industry_pass)
    score = weighted_score(emp, rev, hq, bucket, industry_pass)
    if legacy["decision"] == "Qualified":
        legacy["score"] = score
        return legacy
    if score >= SCORE_THRESHOLD:
        return {"decision":"Qualified","reason":f"{company} passes weighted score ({score} >= {SCORE_THRESHOLD}).","confidence":f"{int(score)}%","score":score}
    out = legacy
    out["score"] = score
    return out

# -------------------------
# Checkpointing
# -------------------------
def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        return load_json(CHECKPOINT_FILE)
    return {"processed_indices": [], "last_saved": None}

def save_checkpoint(processed_indices):
    obj = {"processed_indices": processed_indices, "last_saved": time.time()}
    save_json(CHECKPOINT_FILE, obj)

# -------------------------
# Main processing (sequential, stable)
# -------------------------
def process_dataframe(df: pd.DataFrame, debug: bool=False):
    checkpoint = load_checkpoint()
    processed = set(checkpoint.get("processed_indices", []))
    results = []
    seen_urls = set()

    # resume partials if present
    if Path(PARTIAL_CSV).exists():
        try:
            partial_df = pd.read_csv(PARTIAL_CSV)
            results = partial_df.to_dict(orient="records")
            if '_source_index' in partial_df.columns:
                processed |= set(partial_df['_source_index'].astype(int).tolist())
            seen_urls |= set([r.get("url","") for r in results if r.get("url")])
        except Exception:
            pass

    total = len(df)
    for idx, row in df.iterrows():
        if idx in processed:
            if debug:
                print(f"Skipping already processed index {idx}")
            continue
        try:
            company = str(row.get("company","")).strip()
            title = str(row.get("title","")).strip()
            url = str(row.get("url","")).strip() if "url" in row.index else ""
            if not title or not company:
                if debug:
                    print(f"Skipping idx {idx}: missing title/company")
                processed.add(idx)
                continue

            if url and url in seen_urls:
                if debug:
                    print(f"Skipping idx {idx}: duplicate URL")
                processed.add(idx)
                continue

            print(f"[{idx+1}/{total}] Processing: {company} — {title}")

            if not is_game_role(title):
                rec = {
                    "company":company,"title":title,"detailed_service":"Non-Game Role","service_bucket":"None",
                    "hq":"Unknown","employees":"Unknown","revenue":"Unknown",
                    "industry_match":False,"decision":"Not Qualified","reason":"Role not related to game development.",
                    "confidence":"100%","score":0,"url":url,"_source_index":idx
                }
                results.append(rec)
                processed.add(idx)
                if url:
                    seen_urls.add(url)
            else:
                svc = classify_service(title)
                info = get_company_info(company)
                industry_pass = detect_industry(company, title)
                dec = decide(company, svc["service_bucket"], svc["detailed_service"], info["hq_country"], info["employees"], info["revenue"], industry_pass)
                rec = {
                    "company":company,"title":title,
                    "detailed_service":svc["detailed_service"],"service_bucket":svc["service_bucket"],
                    "hq":info["hq_country"],"employees":info["employees"],"revenue":info["revenue"],
                    "industry_match":industry_pass,"decision":dec["decision"],"reason":dec.get("reason",""),
                    "confidence":dec.get("confidence", "75%"),"score":dec.get("score", weighted_score(info["employees"], info["revenue"], info["hq_country"], svc["service_bucket"], industry_pass)),
                    "url":url,"_source_index":idx
                }
                results.append(rec)
                processed.add(idx)
                if url:
                    seen_urls.add(url)

            if len(processed) % SAVE_EVERY_N == 0 or len(processed) == total:
                pd.DataFrame(results).to_csv(PARTIAL_CSV, index=False)
                save_checkpoint(list(processed))
                save_json(COMPANY_CACHE_FILE, company_cache)
                save_json(INDUSTRY_CACHE_FILE, industry_cache)
                save_json(CLASSIFY_CACHE_FILE, classify_cache)
                if debug:
                    print(f"Checkpoint saved — processed {len(processed)} / {total}")

            time.sleep(random.uniform(0.05, 0.15))

        except Exception as e:
            print(f"Error processing index {idx}: {e}")
            traceback.print_exc()
            pd.DataFrame(results).to_csv(PARTIAL_CSV, index=False)
            save_checkpoint(list(processed))
            save_json(COMPANY_CACHE_FILE, company_cache)
            save_json(INDUSTRY_CACHE_FILE, industry_cache)
            save_json(CLASSIFY_CACHE_FILE, classify_cache)
            continue

    final_df = pd.DataFrame(results)
    final_df.to_excel(OUTPUT_XLSX, index=False)
    pd.DataFrame(results).to_csv(PARTIAL_CSV, index=False)
    save_checkpoint(list(processed))
    save_json(COMPANY_CACHE_FILE, company_cache)
    save_json(INDUSTRY_CACHE_FILE, industry_cache)
    save_json(CLASSIFY_CACHE_FILE, classify_cache)
    print(f"\n🎉 All done — {len(results)} rows processed. Output: {OUTPUT_XLSX}")
    return final_df

# -------------------------
# Streamlit wrapper / single-run helper (backwards compatible)
# -------------------------
def run_icp_engine_logic(company: str, title: str):
    if not is_game_role(title):
        return (
            0, "Not Qualified", "Role not related to game development.",
            "None", "Non-Game Role",
            "Unknown", "Unknown", "Unknown",
            False, "100%"
        )
    svc = classify_service(title)
    info = get_company_info(company)
    industry_pass = detect_industry(company, title)
    dec = decide(company, svc["service_bucket"], svc["detailed_service"], info["hq_country"], info["employees"], info["revenue"], industry_pass)
    return (
        dec.get("score", 0),
        dec["decision"],
        dec.get("reason", ""),
        svc["service_bucket"],
        svc["detailed_service"],
        info["hq_country"],
        info["employees"],
        info["revenue"],
        industry_pass,
        dec.get("confidence", "95%")
    )

def run_qualification(df, debug=False):
    results = []
    total = len(df)
    try:
        import streamlit as st
        using_streamlit = True
        if "process_bar" not in st.session_state:
            st.session_state.process_bar = st.progress(0)
        if "process_text" not in st.session_state:
            st.session_state.process_text = st.empty()
    except Exception:
        using_streamlit = False

    for idx, row in df.iterrows():
        company = row.get("company", "")
        title = row.get("title", "")
        url = row.get("url", "")
        score, decision, reason, bucket, detailed, hq, emp, rev, industry, confidence = run_icp_engine_logic(company, title)
        results.append({
            "company": company,
            "title": title,
            "detailed_service": detailed,
            "service_bucket": bucket,
            "hq": hq,
            "employees": emp,
            "revenue": rev,
            "industry_match": industry,
            "decision": decision,
            "reason": reason,
            "confidence": confidence,
            "score": score,
            "url": url,
            "_source_index": idx
        })

        if using_streamlit:
            st.session_state.process_text.markdown(f"🔄 Processing **{idx+1}/{total}** jobs...")
            st.session_state.process_bar.progress((idx + 1) / total)

        time.sleep(0.05)

    return pd.DataFrame(results)

# -------------------------
# Standalone run
# -------------------------
if __name__ == "__main__":
    if Path(INPUT_FILE).exists():
        df = pd.read_excel(INPUT_FILE)
        out = process_dataframe(df)
        print(out.head())
    else:
        print("Input file not present. Use run_qualification() from Streamlit.")
