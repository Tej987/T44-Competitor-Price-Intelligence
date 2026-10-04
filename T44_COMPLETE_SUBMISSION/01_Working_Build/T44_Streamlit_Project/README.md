# T44 Competitor Price Intelligence

Mini project for Task T44 - AI Text Analytics.

## What this project does
The Streamlit app analyses the supplied competitor price tracker and converts 400 seller rows into 100 comparable observations (Our Brand + Competitor A + B + C). It calculates a transparent three-competitor benchmark, price gaps, category/platform/product signals, latest-week actions, same-platform coverage and verification checks.

### Core formulas
- Competitor benchmark = `(Competitor A + Competitor B + Competitor C) / 3`
- Price gap = `Our Brand price - competitor benchmark`
- Price gap % = `price gap / competitor benchmark * 100`
- Positive gap = Our Brand is more expensive; negative gap = cheaper.

## Run locally
```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app automatically uses `T44_Competitor_price_intelligence_brief.xlsx` when no workbook is uploaded. The upload control is an optional override for another workbook with the same schema.

## Verification
Run:
```powershell
python test_core.py
```
Expected core result:
- 400 source rows -> 100 observations
- benchmark and gap formulas verified
- Excel export generated
- 49 overpriced / 51 underpriced
- overall average gap about -0.66%
- same-platform coverage about 58%

## Main files
- `app.py` - Streamlit interface
- `analysis_core.py` - deterministic calculations, validation, recommendations and export logic
- `test_core.py` - end-to-end verification
- `T44_Competitor_price_intelligence_brief.xlsx` - assigned synthetic dataset
- `T44_Competitor_Price_Intelligence_FINAL.xlsx` - completed workbook with analysis and AI Use Log
- `T44_Competitor_Price_Intelligence_Report.pdf` - 5-page final report
- `AI_PROMPTS_USED.md` - prompt/iteration log
- `DEMO_SCRIPT.md` - 3-5 minute demo guide

## AI-use approach
Python performs the numerical calculations. ChatGPT was used for interpretation, drafting, critique, debugging and iteration. Numeric claims are checked against the deterministic output before acceptance.
