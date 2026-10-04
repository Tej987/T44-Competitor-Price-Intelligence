# T44 AI Prompts Used - Project Development Log

> Evidence note: these are the actual user prompts from the project chat. The PDF transcript is a reconstructed evidence document, not a screenshot of the ChatGPT UI.

## Entry 01 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** How to download this full workbook all things all tabs
**What the output did well / badly:** Explained that downloading as .xlsx preserves all workbook tabs, unlike CSV.
**What changed next and why:** Downloaded the full workbook so the Task Brief, Price Tracker and AI Use Log remained together.
**Decision:** Kept

## Entry 02 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** See my tasks and help me with it
**What the output did well / badly:** Identified T44, the objectives, deliverables and evaluation logic from the workbook.
**What changed next and why:** Uploaded the assigned T44 workbook so the analysis could use the actual dataset.
**Decision:** Kept

## Entry 03 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** See
**What the output did well / badly:** Analysed the attached T44 dataset and produced an initial workbook-oriented solution.
**What changed next and why:** Recognised that a static workbook might be weaker for the working-build criterion, so the approach was challenged and revised.
**Decision:** Partly kept

## Entry 04 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** Bro we have to code also wtf ??
**What the output did well / badly:** Clarified that coding was not explicitly required, but a Streamlit working build would provide stronger evidence for the rubric.
**What changed next and why:** Requested a coded application instead of relying only on a static workbook.
**Decision:** Kept

## Entry 05 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** Yes do it now
**What the output did well / badly:** Generated the first Streamlit implementation using the real T44 dataset and deterministic price-gap calculations.
**What changed next and why:** Ran the app locally and moved to testing/debugging rather than accepting the first build unchanged.
**Decision:** Kept

## Entry 06 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** What to do now that i opeened it in vs code
**What the output did well / badly:** Provided the exact VS Code terminal workflow and explained that app.py should be launched through Streamlit.
**What changed next and why:** Installed the required packages and launched the application locally.
**Decision:** Kept

## Entry 07 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** It worked but this came at end
**What the output did well / badly:** Diagnosed the missing xlsxwriter dependency from the error and explained why the app failed only at export.
**What changed next and why:** Installed xlsxwriter and made sure the dependency was included for the final project.
**Decision:** Kept

## Entry 08 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** See this video what improvement we can do here
**What the output did well / badly:** Reviewed the V1 app and identified business-communication weaknesses: too much table-first output, weak action emphasis and insufficient visual signalling.
**What changed next and why:** Requested a second iteration with executive KPIs, an Action Centre, threshold guides, AI workflow and stronger verification.
**Decision:** Kept

## Entry 09 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** so give me updated best code include everything
**What the output did well / badly:** Produced the V2 Streamlit build with executive dashboard, latest-week KPIs, risk/opportunity analysis, verification and improved export.
**What changed next and why:** Tested V2 locally instead of treating generated code as final.
**Decision:** Kept

## Entry 10 - 2026-10-01
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** Updated Command
**What the output did well / badly:** Adjusted the launch command to the actual D:\AI Project 2\T44_Streamlit_Project_V2 location.
**What changed next and why:** Used the corrected command and confirmed the app launched at localhost:8501.
**Decision:** Kept

## Entry 11 - 2026-10-04
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** So i need to upload it o github should i check it once
**What the output did well / badly:** Recommended final QA before GitHub: app run, filters, tabs, export, refresh and unit test.
**What changed next and why:** Ran test_core.py and checked the UI before considering the repository ready.
**Decision:** Kept

## Entry 12 - 2026-10-04
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** should i test this ouput came
**What the output did well / badly:** Reviewed the rendered dashboard output and identified what was correct plus interpretation/print-layout cautions.
**What changed next and why:** Ran the formal test script rather than relying only on visual inspection.
**Decision:** Kept

## Entry 13 - 2026-10-04
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** all good but it is using my excel sheet or not cause we have an upload option
**What the output did well / badly:** Verified the fallback logic: the bundled T44 workbook is used when no file is uploaded, while the upload control acts as an override.
**What changed next and why:** Kept the upload feature because it makes the tool reusable without changing the assigned default dataset.
**Decision:** Kept

## Entry 14 - 2026-10-04
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** So i can upload this?
**What the output did well / badly:** Reviewed the project ZIP and identified cleanup issues including __pycache__ and a machine-specific path in README.
**What changed next and why:** Cleaned the package, added .gitignore and prepared a GitHub-ready structure.
**Decision:** Kept

## Entry 15 - 2026-10-04
**Tool / model:** ChatGPT - GPT-5.6 Sol
**Exact prompt:** but we need some more files written in instruction right like  reprt AI prompt used etc?
**What the output did well / badly:** Re-read the actual Task Brief and confirmed the four required submission items, including the minimum-15-entry AI Use Log and 3-5 page report.
**What changed next and why:** Expanded the deliverable from code-only to a complete submission package with final workbook, report, AI evidence and demo material.
**Decision:** Kept
