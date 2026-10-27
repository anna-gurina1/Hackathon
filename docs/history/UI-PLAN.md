> **История предыдущих обновлений.** Это не текущая инструкция запуска. Актуальные документы: [README](../../README.md), [START-HERE](../../START-HERE.md), [отчёт рефакторинга](../../REFACTOR-REPORT.md).

# UI implementation plan
Preserve the existing Bitwise identity; this is workflow integration, not redesign.
- White #FFFFFF: page and form surfaces.
- Lilac #F7F4FB: selected workspace and supporting notes.
- Black #000000: primary text.
- Purple #7D39EB: links, focus and workspace identity.
- Lime #C6FF33: primary actions; keep black text.
- Muted #5B5466: explanatory text.
Typography stays Manrope (body) / Unbounded (headings), with system fallbacks.
Use existing container/card/field/button patterns. Company name and role stay visible
above company tools, not just in a closed avatar menu. Team controls stack on mobile.
Separate personal account, company settings, invitation inbox, and course assignments.
No decorative graphics or animation; focus, labels, and reduced motion matter more.
Review: information is specific to a course-authoring workflow, no generic dashboard
widgets added. Reuse existing styles; add only responsive workspace controls.

## Workspace context correction
Keep the existing white/lime/purple palette and typography. Remove the redundant
Switch button; use a labelled native select with an advance navigation hint and
CSRF-protected POST on change. Preserve a no-JS submit fallback. Personal mode
shows learner controls only, even on one's own course. Selected-company mode
shows that company's author tools, plus a clear Take as a learner transition.
Preview links never create enrollment or results. No new decorative UI.
