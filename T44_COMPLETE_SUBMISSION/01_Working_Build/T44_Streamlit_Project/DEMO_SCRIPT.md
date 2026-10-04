# 3–5 Minute Demo Script — T44 V2

**Opening**
“My project is a competitor price-intelligence tool. It converts 400 source seller rows into 100 comparable observations, where each observation has Our Brand plus Competitor A, B and C.”

**Method**
“For each observation, Python calculates the arithmetic mean of the three competitor prices. I subtract that benchmark from Our Brand’s price and normalize it as a percentage. Positive means we are priced above benchmark; negative means below.”

**Dashboard**
“The executive screen immediately shows the overall position, the latest week, threshold-based action items, trends, category signals and the largest pricing risks and opportunities. Red indicates a premium to benchmark; green indicates a discount.”

**Business action**
“I use a configurable absolute-gap threshold to prioritise review. This is deliberately not an automatic repricing rule. Before action, the manager should validate stock, promotions, margin and platform comparability.”

**Data quality**
“I also report same-platform competitor coverage separately. This matters because marketplace, own-site and quick-commerce offers are not always perfectly comparable.”

**AI use**
“The numerical analysis is deterministic Python. AI is used for text analytics: I supply only verified metrics to an LLM to generate the weekly management brief. I then extract and verify its numeric claims before accepting the narrative.”

**Verification**
“The verification tab proves the benchmark uses A, B and C, recomputes both gap formulas, confirms source-row traceability, and provides manual spot-check examples.”

**Close**
“So the project is not just a dashboard. It is a controlled workflow: raw data → verified calculations → decision signals → LLM narrative → human verification → exportable management output.”
