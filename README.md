# 💧 Reservoir Rule Curve Optimizer
### CWC-Compliant Backward Calculation · 10 Flood-Cushion Cases · Excel + PDF Export

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://rule-curve-creator-as-per-cwc-guidelines-6qruf2pn9ysybdb9gypwv.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Method: CWC](https://img.shields.io/badge/Method-CWC%20Backward%20Calculation-orange.svg)](https://cwc.gov.in)

---

## 🚀 Try It Now — Free, No Login

**[▶ Open Live App](https://rule-curve-creator-as-per-cwc-guidelines-6qruf2pn9ysybdb9gypwv.streamlit.app/)**

Upload your reservoir data → Get rule curves in under 2 minutes.
No installation. No account. Works on any device.

---

## What Problem Does This Solve?

Designing reservoir rule curves manually following CWC guidelines takes:
- **3–6 months** using traditional consultant-led studies
- **₹8–20 Lakhs** per reservoir in consultant fees
- Multiple Excel files, manual backward calculations, and prone to errors

This tool reduces that to **under 2 minutes** with a single web interface — producing the same CWC-compliant output with full traceability.

---

## Key Features

- **10-Case Flood Cushion Analysis** — evaluates flood cushion from 0.0 ft to 4.5 ft below FRL simultaneously, giving engineers the full tradeoff picture
- **Backward Calculation Engine** — implements CWC's standard method exactly: `S[t] = MIN(Cap, MAX(MDDL_S, S[t+1] − Q[t+1] + D[t+1]))`
- **Dual Rule Curve Design** — Upper RC (P50 inflows, flood control) and Lower RC (P10 inflows, drought protection)
- **Forward Simulation** — verifies Cases 1, 5, and 10 against annual inflow-demand mass balance
- **7-Sheet Excel Export** — PKm-style formatted workbook: Summary, Demand, Inflows, Upper RC (all cases), Lower RC (all cases), Demand Satisfaction, Cross-Comparison
- **PDF Report** — 8-section professional report ready for Dam Safety Authority submission
- **Interactive Charts** — Plotly-powered rule curve visualization with flood cushion zone shading, anchor period markers, and case comparison
- **Sample Data Included** — Bhavanisagar Reservoir (Bhavani River, Tamil Nadu) pre-loaded for immediate testing
- **Upload Your Own Data** — ES curve CSV, inflow CSV, demand CSV — any reservoir

---

## Quick Start (3 Steps)

**Option A: Use the Live Web App (Recommended)**

```
1. Open: https://rule-curve-creator-as-per-cwc-guidelines-6qruf2pn9ysybdb9gypwv.streamlit.app/
2. Click "Use sample data" for ES curve and Inflows (or upload your own CSV)
3. Click "🚀 RUN OPTIMIZATION" → View results across 6 tabs → Download Excel + PDF
```

**Option B: Run Locally**

```bash
# Clone
git clone https://github.com/mtechiisc2325-stack/rule-curve-creator-as-per-cwc-guidelines.git
cd rule-curve-creator-as-per-cwc-guidelines

# Install
pip install -r requirements.txt

# Run
py -3.12 -m streamlit run streamlit_app.py
# Opens at http://localhost:8501
```

---

## Input Data Format

### 1. Elevation-Storage (ES) Curve
CSV file, 2 columns, no header required:
```
91.00, 10
95.33, 130
107.59, 807
```
Minimum 3 pairs. Values must be monotonically increasing.

### 2. Inflows & Demand
CSV file, 36 rows × 3 columns (P50 inflow, P10 inflow, demand — all in MCM/decade):
```
72, 15, 16
95, 40, 14
128, 65, 18
...
```
36 rows = one per 10-day period from Jul-I to Jun-III (Indian water year).

### 3. Reservoir Parameters (entered in sidebar)
- **FRL** — Full Reservoir Level in metres
- **MDDL** — Minimum Drawdown Level in metres
- **Reservoir name, river name** (for reports)

---

## Output Sheets (Excel Workbook)

| Sheet | Contents |
|---|---|
| `1_Summary` | Reservoir parameters + all 10 cases ranked by flood risk score |
| `2_Demand` | 36-period demand with annual fraction and zone remarks |
| `3_Inflows` | P50 & P10 inflows vs demand, Surplus/Moderate/Deficit status |
| `4_UpperRC_AllCases` | Upper rule curve levels (m) for all 10 cases × 36 periods |
| `5_LowerRC_AllCases` | Lower rule curve levels (m) for all 10 cases × 36 periods |
| `6_DemSat_AllCases` | Supply (MCM) and satisfaction (%) for all 10 cases |
| `10_CrossComparison` | Side-by-side URC level comparison — all cases, all periods |

Color coding: 🔵 Flood cushion zone (Aug-III–Oct-III) · 🔴 Anchor periods · 🟢 High satisfaction · 🟡 Moderate · 🔴 Low

---

## The 10-Case Optimization

The key variable is **flood cushion** — how far below FRL to keep the reservoir during peak monsoon (Aug–Oct) to absorb late-monsoon rainfall without spillway operation.

| Case | Cushion | Nov-II Target | Flood Space | Drought Risk |
|------|---------|---------------|-------------|--------------|
| 1 | 0.0 ft | FRL (max supply) | 0 MCM | Minimum |
| 2 | 0.5 ft | FRL − 0.15 m | ~4 MCM | Very Low |
| 3 | 1.0 ft | FRL − 0.30 m | ~9 MCM | Low |
| 4 | 1.5 ft | FRL − 0.46 m | ~13 MCM | Low-Moderate |
| **5** | **2.0 ft** | **FRL − 0.61 m** | **~18 MCM** | **Moderate ★** |
| 6 | 2.5 ft | FRL − 0.76 m | ~29 MCM | Moderate-High |
| 7 | 3.0 ft | FRL − 0.91 m | ~40 MCM | High |
| 8 | 3.5 ft | FRL − 1.07 m | ~50 MCM | High |
| 9 | 4.0 ft | FRL − 1.22 m | ~61 MCM | Very High |
| 10 | 4.5 ft | FRL − 1.37 m | ~72 MCM | Maximum |

★ Case 5 (2.0 ft) is the default recommendation. Override based on downstream population density and flood damage history.

---

## Methodology

### Backward Calculation Formula (CWC Standard Method)

```
For each period t (working backward from anchor):

S[t] = MIN( Cap[t], MAX( MDDL_Storage, S[t+1] − Q[t+1] + D[t+1] ) )

Where:
  S[t]      = Required storage at start of period t (MCM)
  S[t+1]    = Storage required at next period (MCM)
  Q[t+1]    = Inflow during period t+1 (P50 for URC, P10 for LRC)
  D[t+1]    = Water demand during period t+1 (MCM)
  Cap[t]    = FRL_Storage (normal) or Cushion_Target (flood cushion zone)
  MDDL_S    = Minimum drawdown storage (lower bound)
```

### Anchor Points

| Curve | Anchor Period | Anchor Storage | Inflow Basis |
|-------|--------------|----------------|--------------|
| Upper RC | Nov-II (PID 13) | FRL − cushion | P50 (50% dependable) |
| Lower RC | May-III (PID 32) | MDDL | P10 (90% dependable) |

### Flood Cushion Zone
Periods Aug-III to Oct-III (PID 5–11): reservoir is held below FRL to create absorption capacity for late-monsoon rain events.

---

## Repository Structure

```
rule-curve-creator-as-per-cwc-guidelines/
│
├── streamlit_app.py          # Main web application (6 interactive tabs)
├── requirements.txt          # Python dependencies
├── README.md                 # This file
│
└── src/
    ├── constants.py          # 36 water-year periods, sample data
    ├── es_curve.py           # Elevation↔Storage interpolation (scipy)
    ├── rule_curve_calc.py    # Backward calculation engine (all 10 cases)
    ├── simulation.py         # Forward simulation (Cases 1, 5, 10)
    ├── report_generator.py   # PDF report (ReportLab)
    └── excel_exporter.py     # 7-sheet Excel workbook (openpyxl)
```

---

## Tech Stack

| Component | Library | Purpose |
|---|---|---|
| Web UI | Streamlit | Interactive frontend |
| Hydrology engine | NumPy, SciPy | Backward calculation, interpolation |
| Data handling | Pandas | Period tables, ES curves |
| Charts | Plotly | Interactive rule curve visualization |
| Excel export | openpyxl | 7-sheet formatted workbook |
| PDF export | ReportLab | Professional report generation |

---

## Use Cases

- **State Water Resources Departments** — design or update rule curves for reservoirs under dam safety review
- **Consulting Engineers** — reduce study timelines from months to days; generate CWC-compliant deliverables quickly
- **Dam Safety Officers** — evaluate flood cushion adequacy for SDSO submissions
- **Academic Research** — teach reservoir systems engineering with a live tool (IIT, NIT, universities)
- **Project Feasibility Studies** — rapid rule curve assessment for new reservoir planning

---

## Case Study: Bhavanisagar Reservoir

Sample data included in the app (pre-loaded by default):

| Parameter | Value |
|---|---|
| River | Bhavani River, Tamil Nadu |
| FRL | 107.59 m |
| MDDL | 95.33 m |
| Live Storage | 677 MCM |
| Annual P50 Inflow | 2,572 MCM |
| Annual Demand | 827 MCM |
| Recommended Case | Case 5 (2.0 ft, 18 MCM flood space) |

---

## Consulting & Support

Need rule curves designed for your reservoir?

**Services available:**
- Rule Curve Design Package — ES curve + inflows → 7-sheet Excel + PDF report (₹15,000–25,000)
- Training Workshop — 2-day hands-on workshop for WRD teams (₹1–2 L per batch)
- Institutional License — Annual license for academic use (₹25,000–50,000/year)

📧 Contact: **mtechiisc2325@gmail.com**

---

## Citation

If you use this tool in research or official reports, please cite:

```
Karthikeyan, [First Name]. (2026). Reservoir Rule Curve Optimizer: 
CWC-Compliant Backward Calculation Tool [Software]. 
GitHub. https://github.com/mtechiisc2325-stack/rule-curve-creator-as-per-cwc-guidelines
```

Related publication:
> Karthikeyan et al. (2026). *Cascade breach analysis of Upper and Lower Aliyar Dams 
> using HEC-RAS 2D under CMIP6 scenarios.* ICDS 2026, IISc Bengaluru.

---

## Contributing

Contributions welcome. Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-analysis`)
3. Commit your changes (`git commit -m 'Add new analysis type'`)
4. Push to the branch (`git push origin feature/new-analysis`)
5. Open a Pull Request

Bug reports and feature requests: [Open an issue](https://github.com/mtechiisc2325-stack/rule-curve-creator-as-per-cwc-guidelines/issues)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

**Disclaimer:** This tool is developed independently using published CWC engineering guidelines. It is not an official product of the Water Resources Department, Tamil Nadu, the State Dam Safety Organisation (SDSO), or the Government of India. All outputs must be reviewed and endorsed by a qualified engineer before use in official submissions or dam safety reports.

---

## Acknowledgements

- Central Water Commission (CWC) — Reservoir design guidelines and backward calculation methodology
- IISc Bengaluru — MTech Dam Engineering program (inspiration and domain foundation)
- Bhavanisagar Dam, Tamil Nadu — Sample reservoir dataset

---

*Built by a dam safety engineer, for dam safety engineers.*
*Questions? Open an issue or email mtechiisc2325@gmail.com*
