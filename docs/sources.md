# Source research (Milestone 1)

Research date: **2026-11-08**. Every URL, count and header value below was fetched and seen on that
date, unless it is marked **not verified**. Nothing here is guessed. Fixture files are the exact
bytes the server returned (line endings included, but see "Git note" at the end).

User-Agent used: `OpenNaksha-research/0.1 (open-source TP map catalog; non-commercial)`.
Rate: at least 1.2 s between requests to the same host. All requests had a 30–40 s timeout.
PDFs were checked with `HEAD` only. Nothing large was downloaded.

## Summary

| Authority | Base URL | Listing found? | JS needed? | TLS | File headers (HEAD) | Verdict |
|---|---|---|---|---|---|---|
| **SMC** (Surat Municipal Corp.) | https://www.suratmunicipal.gov.in | Yes. One page has all 146 TP schemes in 4 status tables (map, B/F-form, notifications) | No | OK | ETag + Last-Modified + Content-Length | **yes** |
| **SUDA** (Surat Urban Dev. Auth.) | https://www.sudaonline.org | Yes. 2 pages, 33 schemes (sanctioned draft, preliminary, submitted) | No | OK | ETag + Last-Modified + Content-Length | **yes** |
| **AMC** (Ahmedabad Municipal Corp.) | https://ahmedabadcity.gov.in | Yes. One table of 287 schemes with status and date, plus a few draft-TP links in the menu | No | OK | `/Uploads/TpInfo/*.pdf`: ETag + LM + CL. `/ViewFile/…`: CL only | **yes** (messy HTML) |
| **AUDA** (Ahmedabad Urban Dev. Auth.) | https://www.auda.org.in | Yes. One table of 94 schemes with draft/prelim/final dates, map JPG and F-form PDF | No (map URL is in a hidden input) | OK | ETag + Last-Modified + Content-Length | **yes** |
| **VMC** (Vadodara Municipal Corp.) | https://vmc.gov.in | Link lists only (no table): 33 draft, 10 prelim, 3 F-form, 33 final | No | OK | Last-Modified + CL, **no ETag** | **partial** |
| **VUDA** (Vadodara Urban Dev. Auth.) | https://www.vuda.co.in | Link lists in 4 status pages (folder per scheme), plus a legacy page and home-page links | No (the main menu is JS, but the pages are plain HTML) | OK | ETag + Last-Modified + Content-Length | **partial** |
| **RMC** (Rajkot Municipal Corp.) | https://egov.rmc.gov.in/TPMAP | Yes. 68 schemes, name + status in the link text, one map link each | No | OK | **Content-Length only**. Opaque encrypted file tokens | **partial** |
| **RUDA** (Rajkot Urban Dev. Auth.) | https://rajkotuda.com | Yes. One small table of 11 recent schemes with dates, plan and F-form | No | OK | ETag + Last-Modified + Content-Length | **yes** (small) |
| **TPVD** (state Town Planning & Valuation Dept.) | https://townplanning.gujarat.gov.in | No scheme/map listing. Has a statewide **notifications** table (107 rows, PDFs) | No | OK | `HEAD` gives **405**, so GET is needed | **partial** (notifications only, no maps) |

Robots.txt: **none of the hosts has a robots.txt** (all return 404, or a 404 page). The one
exception is sudaonline.org, which only disallows `/wp-admin/`. So nothing we need is disallowed.

---

## 1. Surat — SMC (most important; first scraper)

- **Base URL:** `https://www.suratmunicipal.gov.in` (ASP.NET MVC on IIS)
- **robots.txt:** `https://www.suratmunicipal.gov.in/robots.txt` returns **404** (an HTML "Page Not Found" page). No restrictions.
- **TLS:** fine, no `-k` needed.
- **JavaScript:** **not needed.** All tables are server-rendered. JS only fills the "(Total Schemes: N)" badge counts.
- **Language:** English. Scheme names are uppercase or mixed-case English transliterations. There is no Gujarati version (only a Google Translate widget).
- **Navigation:** Home → Departments → Engineering → Town Planning (`/Departments/TownPlanningHome`). Left menu items: "TP Details" (`/Departments/TownPlanningTPDetails`) and "Development Plans" (`/Departments/TownPlanningDevelopmentPlans`).

### 1.1 Listing pages (verified)

| URL | What | Rows |
|---|---|---|
| `https://www.suratmunicipal.gov.in/Departments/TownPlanningAllTPSchemes` | **Main listing**: all 4 status tables on one page. A scraper needs only this page. | 74 + 18 + 49 + 5 = **146** |
| `/Departments/TownPlanningTPDetails` | Summary: count and area per status, plus 5 "Status" PDFs | 4 + total |
| `/Departments/TownPlanningSanctionedFinalSchemes` | Same table as section 1 of the main page | 74 |
| `/Departments/TownPlanningPreliminarySchemes` | Same table as section 2 | 18 |
| `/Departments/TownPlanningDraftSchemes` | Same table as section 3 | 49 |
| `/Departments/TownPlanningDraftSchemesSubmitToGov` | Same table as section 4 | 5 |
| `/notifications/Notifications?Id=<Id>` | Per-scheme detail page: notification documents per TP stage | varies |
| `/Departments/TownPlanningDevelopmentPlans` | DP sheets A–Z as ZIP files (26 rows) | 26 |

I checked that every file/notification link on the 4 per-status pages also appears on
`TownPlanningAllTPSchemes`. The counts match the TP Details summary (74 / 18 / 49 / 5 = 146).
**No pagination.**

### 1.2 HTML structure of `TownPlanningAllTPSchemes` (fixture `smc/tp_all_schemes.html`)

There are 4 collapsible sections. Each is `div.well-custom-body` > inner `div#<id>` > `div.table-responsive` > `table.table.table-bordered.table-customized.automatic-counter`.

| Order | Wrapper div id | Inner div id | `<caption class="hidden">` text | Catalog status | 6th column header |
|---|---|---|---|---|---|
| 1 | `FinalSchemesWrapper` | `FinalSchemes` | "Details of Sanctioned Final Schemes" | `final` | B-Form |
| 2 | `SanctionedPreliminarySchemes` | `PreliminarySchemes` | "Details of Sanctioned Preliminary Town Planning Schemes" | `preliminary` | Redistribution Statement |
| 3 | `DraftSchemes` | `DraftSchemes` (**same id twice, nested**) | "Details of Draft Schemes - Pending with Town Planing Officer" | `draft` (sanctioned draft) | F-Form |
| 4 | `DraftSchemesSubmittedtoGovt` | `DraftSchemesGovtSanction` | "Details of Draft Schemes submitted to Govt. for sanction" | `draft` (submitted, not yet sanctioned) | F-Form |

The section header buttons say "Sanctioned Final Schemes", "Sanctioned Preliminary Schemes", "Draft Schemes",
"Draft Schemes submitted to Govt. for sanction". The TP Details page calls section 3 "Sanctioned Draft Schemes".

**Tip:** pick the tables by order (`soup.select("table.table-customized")` gives exactly 4) or by
caption text. Do not use `#DraftSchemes`, because that id is duplicated.

**Columns (all 4 tables):** `Sr. No` | `Name` | `Area in Hectare` | `Notifications` | `Map` | `B-Form` / `Redistribution Statement` / `F-Form`

- `thead` has the header row. `tbody` has the data rows, and the **last row is a total row** (`<tr class="text-bold total">`, 2nd cell "Total"). Skip it.
- **Sr. No cell is empty** (`<td class="text-center">&nbsp;</td>`). The numbers are added by CSS (`automatic-counter`). Don't rely on them.
- **Name cell** has scheme number and area name in one string, with varying spellings (all seen):
  `T.P.S.NO.1 (Laldarwaja)`, `T.P.S.NO.3. (RUNDH)`, `T.P.S.NO. 14 (RANDER-ADAJAN)`,
  `T.P.S.NO.85(SARTHANA-PASODRA-LASKANA)` (no space), `T.P.S 91 (VESU)`, `T.P.S. 95 (GHABHENI)`,
  `T.P.S.NO.84 (KOSAD-BHARTHANA KOSAD-MOTAVARACHHA-ABRAMA)`. There are stray spaces and `&nbsp;`, so strip them.
  A pattern that fits all 146: `T\.?P\.?S\.?\s*(?:NO\.?)?\s*(\d+)\.?\s*\((.+)\)`.
- **Scheme numbers are NOT unique**: the same number is reused for different villages, even within one
  status. Examples: final has `T.P.S.NO.1 (Laldarwaja)`, `T.P.S.NO.1 (Udhna-Majura)`, `T.P.S.NO.1 (VESU)`;
  draft has `T.P.S.NO.33 (DUMBHAL)` and `T.P.S.NO.33 (TALANGPOR-UMBER)`. **Number + area name** is the unique key
  (see "Catalog impact" below).
- **Area** cell: decimal hectares as text (`40.87`, `208.9`), sometimes followed by `&nbsp;`.
- **Notifications** cell: `<a target="_blank" href='/notifications/Notifications?Id=TP01 Udhna-Majura'>` with a
  folder icon (no visible text, only `<span class="hidden">View Notification details</span>`). The Id has raw spaces,
  so URL-encode it when you request it. 143 of 146 rows have one. 3 rows have only `&nbsp;` (e.g. TP 1 Laldarwaja, TP 2 Nanpura, TP 6 Majura-Khatodara).
- **Map** and **B/F-Form/Redistribution** cells: `<a target="_blank" href="/Content/Documents/Departments/...pdf" class="no-cache" ...>Map</a>`.
  Links are **root-relative**, with **raw spaces and parentheses** in the path, e.g.
  `/Content/Documents/Departments/FinalSchemes/TP01 Laldarwaja/CTP01(LALDARWAJA)FINAL.pdf`. Encode spaces as `%20` (I verified that this works).
  Sometimes the cell has the label text but **no `<a>`** (TP 3 Rundh: "Map" and "B-Form" as plain text; TP 53 Magob Dumbhal: no B-Form link;
  TP 97 Kumbhariya: empty cells). Treat those as "file not published".
- File path folders by status: `FinalSchemes/`, `PreliminarySchemes/`, `Draftschemes/`, `DraftschemesSTG/`. File names have no fixed
  pattern (`CTP01(UDHANA-MAJURA)FINAL.pdf`, `TP01 VESU.pdf`, `TP94_MOTA_VARACHHA_MAP.pdf`, `TP2 UDHANA PLAN NO-3.pdf`).
  One map is a **JPG**: `/Content/Documents/Departments/FinalSchemes/TP11 PUNA/TP11_PUNA.jpg`. In total there are 286 file links + 143 notification links.
- No dates on the listing (no sanction dates, no status dates). The only date is the page footer
  `<span id="spnLastUpdated">September 08, 2026 12:05 PM</span>`. That is a useful "page changed" hint.

### 1.3 Notifications detail page (fixtures `smc/notifications_*.html`)

`/notifications/Notifications?Id=TP01%20Udhna-Majura` has `<h2>Notifications For TP01 Udhna-Majura</h2>` and then
`table.table.table-bordered.table-striped.table-customized`. It is a **fixed checklist of TP-Act stages**
(1 CTP Consultation, 2 Intention Declaration a–d, 3 Public meeting, 4 Publication a–d, 5 Submission to Government a–b,
6 Government Sanction, 7 TPO Appointment, 8 Award Notification, 9 Preliminary submission, 10 Preliminary Sanction
of Government Notification, 11 Final submission, 12 Final Scheme Sanction of Government Notification, …).
Only the stages with a document have an `<a>`. **The hrefs use Windows backslashes and are relative**:

```html
<a target="_blank" class="no-cache" href='..\Content\Documents\Departments\notifications\TP01 Udhna-Majura\10.pdf'>Preliminary Sanction of Government Notification</a>
```

Browsers turn `\` into `/`. Python's `urljoin` does **not**, so replace `\` with `/` first, then join against
the page URL. That gives `https://www.suratmunicipal.gov.in/Content/Documents/Departments/notifications/TP01%20Udhna-Majura/10.pdf`
(I checked this with HEAD on `.../notifications/TP94_MOTA_VARACHHA/1.pdf`: 200, application/pdf).
File names are the stage numbers (`1.pdf`, `2a.pdf` … `12.pdf`). There are **no dates** on this page. Its footer "Last Updated" is
January 25, 2023, which looks like a template date. TP01 Udhna-Majura has 3 docs (stages 1, 10, 12). TP94 has 12 docs (stages 1–5b).
Fetching 143 of these pages each run is heavy. A suggestion: fetch them only for new schemes, or less often.

### 1.4 File headers (HEAD, verified)

| URL (encoded) | Size | Last-Modified | ETag |
|---|---|---|---|
| `/Content/Documents/Departments/FinalSchemes/TP01%20VESU/TP01%20VESU.pdf` | 158,952 | Tue, 30 Aug 2016 09:09:00 GMT | `"0de3c259e2d21:0"` |
| `/Content/Documents/Departments/FinalSchemes/TP01%20Laldarwaja/CTP01(LALDARWAJA)FINAL.pdf` | 210,888 | Tue, 30 Aug 2016 09:09:00 GMT | `"0de3c259e2d21:0"` |
| `/Content/Documents/Departments/PreliminarySchemes/TP25%20Singanpore-Tunki/TP25%20Singanpore-Tunki.pdf` | 925,009 | Tue, 30 Aug 2016 09:26:00 GMT | `"0843485a02d21:0"` |
| `/Content/Documents/Departments/Draftschemes/TP33%20Dumbhal/CTP33(DUMBHAL)DRAFT.pdf` | 357,932 | Tue, 30 Aug 2016 09:05:00 GMT | `"0c62f969d2d21:0"` |
| `/Content/Documents/Departments/DraftschemesSTG/TP94_MOTA_VARACHHA/TP94_MOTA_VARACHHA_MAP.pdf` | 1,158,336 | Thu, 18 Dec 2025 06:11:00 GMT | `"0f2b614e56fdc1:0"` |
| `/Content/Documents/Departments/notifications/TP94_MOTA_VARACHHA/1.pdf` | 756,341 | Thu, 18 Dec 2025 06:11:00 GMT | `"0f2b614e56fdc1:0"` |
| `/Content/Documents/Departments/AllSchemesStatus.pdf` | 86,812 | Wed, 30 Sep 2026 06:01:00 GMT | `"0b63a11a150dd1:0"` |
| `/Images/Departments/TownPlanning/B-Segvachhama,Malgama,.zip` (DP sheet) | 1,601,095 | Fri, 02 Sep 2016 05:12:00 GMT | `"050b288d84d21:0"` |

All return `Cache-Control: public,max-age=608399` and `Accept-Ranges: bytes`. **Warning: the IIS ETag here
comes from the file timestamp only.** Two different files with the same minute-rounded
mtime share an ETag (the TP01 VESU and TP01 Laldarwaja rows above, and the TP94 map and notification rows).
So use ETag + Content-Length + Last-Modified together, and never treat ETag alone as a content identity.
Map PDFs are small: 0.16–1.2 MB in the samples.

### 1.5 Development Plan (DP)

`/Departments/TownPlanningDevelopmentPlans` has `table.table-customized` with columns `Sheet No.` | `Name`. It has 26 rows (A–Z).
Each name cell has `<a class="sublink1" href="/Images/Departments/TownPlanning/<Letter>-<village list>.zip">` (ZIPs, root-relative,
with commas, an apostrophe and spaces in the path). The page footer says Last Updated October 08, 2019 and the ZIP is dated 2016, so this is an
old DP and not updated. Scrapable, but low value.

### 1.6 Update frequency

Footers: AllTPSchemes Sep 08 2026, per-status pages Sep 01 2026, TP Details Oct 01 2026. The status PDF was modified Sep 30 2026.
The TP94 draft files were added Dec 2025. Old maps are dated 2016 (bulk upload). This looks like a **few updates per year**.
A weekly check is more than enough.

### 1.7 Other (not scraped)

`https://gis.suratmunicipal.org/` (GIS portal, linked from home) was **not examined**.

**Verdict: YES.** It is one static page with 146 schemes, explicit status per table, direct PDF links, and good HTTP headers.

---

## 2. Surat — SUDA

- **Base URL:** `https://www.sudaonline.org` (WordPress, served by Hostinger CDN `Server: hcdn`)
- **robots.txt:** exists. `User-agent: *`, `Disallow: /wp-admin/`, `Allow: /wp-admin/admin-ajax.php`, `Sitemap: https://www.sudaonline.org/wp-sitemap.xml`. Our pages are allowed.
- **TLS:** fine. **JS:** not needed. **WP REST API** (`/wp-json/wp/v2/pages`) returns **401** "restricted to authenticated users", so it can't be used.
- **Language:** English tables. The intention page and some news items are in Gujarati.
- **Menu:** "TP Scheme" (`/services/`) has "Sanction Tp Schemes", "Published TP Scheme", "TP Scheme Intention", "Submitted to Govt. TP Scheme".

### 2.1 Listing pages (verified)

| URL | Content | Rows |
|---|---|---|
| `https://www.sudaonline.org/services/tp-schemes/` ("Sanction Tp Schemes") | **2 tables**: (1) caption "Details of Sanctioned Draft Town Planning Schemes", (2) caption "Details of Sanctioned Preliminary Town Planning Schemes" | 17 + 5 |
| `https://www.sudaonline.org/submitted-to-govt-tp-scheme/` | caption "Details of Draft Town Planning Schemes submitted to Govt. for Sanction" | 11 |
| `https://www.sudaonline.org/services/published-tp-scheme/` | caption "Details of Published Town Planning Schemes". Its **data rows are inside an HTML comment** (`<!--- … -->`), so nothing is visible | 0 visible |
| `https://www.sudaonline.org/services/tp-scheme-intention/` | Gujarati headers (અનુ. નં, ટી.પી.સ્કીમનું નામ, area, consultation date, intention date, MAP). **Only one empty row** | 0 |
| `https://www.sudaonline.org/development-plans/dp-2035-sheet-dt-08-10-2020-corrigendum-9-11-2020/` | DP-2035 sheets as a WordPress gallery of JPGs | 46 |

### 2.2 HTML structure

Every table is `div.entry-content table.table.table-bordered.table-customized.automatic-counter`, with `<thead>` and `<tbody>`.

- **Sanctioned (draft and preliminary) tables:** `Sr. No.` | `Name` | `Area In Hectare` | `Notifications` | `Map` | `F-Form`.
  The Sr. No. is real text here (1, 2, …). The **Notifications cell links directly to a PDF** (`<a class="no-cache" href="https://www.sudaonline.org/wp-content/uploads/2025/12/1-DRAFT-TPS-NO.35KUMBHARIYA-DEVDH-SAROLI-SANIYA-HEMAD.pdf">View Notification details</a>`). There is no detail page.
- **Submitted table:** `Sr. No.` | `Name` | `Area In Hectare` | `Map` | `F-Form` (no notifications column). It has **malformed HTML**: stray extra `<tr>` openers (`<tr>\n<tr>`). A lenient parser gives some empty rows, so skip rows with fewer than 5 `<td>`.
- **Links are absolute** `https://www.sudaonline.org/wp-content/uploads/YYYY/MM/<file>.pdf`. The YYYY/MM is the WordPress upload month, which is a good "first published" hint.
- **Name formats seen:** `T.P.S.NO 35 (Kumbharia-Sania Hemad-Saroli-Devadh)`, `102.(kanad)`, `86.(Vedchha- Niyol)`, `66 ( Dhoran Pardi )`, `70.(kamrej)`,
  `62-A( CHHEDCHHA &#8211; OVIYAN &#8211; SABARGAM &#8211; ANTROLI)` (HTML en-dash entities). Scheme "numbers" can have letter suffixes (`62-A`, `62-B`, `62-C`).
- No dates in the tables.
- **DP-2035 gallery:** each sheet is `dl.gallery-item > dt.gallery-icon > a[href]` pointing to the full JPG (e.g. `https://www.sudaonline.org/wp-content/uploads/2020/11/A.jpg`). The caption is in `data-lbwps-caption` / `dd.gallery-caption` (BASE MAP, A, B, C, C1, … Z). There is also an index map, `INDAX-MAP.jpg`. The images are 8400×8400 px.

### 2.3 File headers (HEAD, verified)

| URL | Size | Last-Modified | ETag |
|---|---|---|---|
| `…/uploads/2026/08/Draft-TPS-86-Vedchha-Niyol-Plan-NO.3.pdf` | **57,169,005 (57 MB)** | Thu, 06 Aug 2026 11:50:37 GMT | `"368546d-6a74750d-7eb486243f16caae;;;"` |
| `…/uploads/2024/07/T.P.S.NO-41-Vav_Plan-3.pdf` | 1,675,081 | Wed, 24 Jul 2024 14:36:52 GMT | `"198f49-66a11184-3064392b48a1b37a;;;"` |
| `…/uploads/2025/08/1.T.P.S.NO-66-Dhoran-paradi-Plan-No.3.pdf` | 876,143 | Fri, 22 Aug 2025 07:37:10 GMT | `"d5e6f-68a81e26-6b65a915bb4e97c5;;;"` |
| `…/uploads/2020/11/A.jpg` (DP sheet) | 606,148 | (not sent) | (not sent) |

Some SUDA map PDFs are **very large** (57 MB), so the pipeline must not hash these often (use HEAD).

### 2.4 Update frequency

Upload folders range from 2024/07 to **2026/08**. Newest: TPS 86 in Aug 2026, TPS 102 in Jul 2026. Several updates per year.

**Verdict: YES.** 33 schemes in static tables with status per table and absolute PDF links. Overlaps with SMC numbering (both have a "TP 86"), so the catalog ID needs the authority/area.

---

## 3. Ahmedabad — AMC

- **Base URL:** `https://ahmedabadcity.gov.in` (ASP.NET on `Microsoft-IIS/10.0`)
- **robots.txt:** none (redirects to `/404.htm?aspxerrorpath=/robots.txt`).
- **TLS:** fine. **JS:** not needed for the table. **Language:** English (uppercase village names).
- **Listing:** `https://ahmedabadcity.gov.in/SP/TPSchemeInformation` ("TP Scheme Information", under menu "City Planning"). It is 361 KB, with one data table and **no pagination**.

### 3.1 Structure (fixture `amc/tp_scheme_information.html`)

The table has **no id or class**. Select it with `div.AMCtable2.TP_Scheme table` (the only one on the page). All rows are in `<tbody>`, and the first row is the `<th>` header:

`Sr No` | `TPS Name` | `TPS No` | `Type` | `Current Status` | `Current Status Date` | `Drawing Name`

- **287 schemes** (Sr No 1–287) in 409 data rows. Varied schemes use **`rowspan`**: the scheme row has `rowspan="N"` on Sr No, TPS Name, TPS No
  (and usually Drawing Name). The next N−1 `<tr>` have only `Type | Current Status | Current Status Date` (e.g. `1ST VARIED | FINAL SANCTIONED | 27/04/2007`).
  Sometimes a varied row also has its own Drawing cell (e.g. TPS 3 Ellisbridge). A few varied rows are irregular (a date where the Type should be,
  or an empty Type). **A proper rowspan-aware table expander is needed.**
- **TPS No** is a string: `1A`, `1B`, `20A`, `35_1`, `37_A`, `38/1`, `43/A`, `401-A`, `152/G`, … (also plain integers). Numbers repeat across villages
  (`1` = Bopal, Chandlodiya, Ghatlodiya, …), so **name + number** is the key.
- **Type:** `PRINCIPAL`, `1ST VARIED` … `8TH VARIED` (also `3rd VARIED`, `-`, empty).
- **Current Status** values on principal rows: `FINAL SANCTIONED` (132), `DRAFT SANCTION` (124), `PRELIMINARY SANCTIONED` (19), `DRAFT SANCTIONED` (10),
  `PRELIMINARY SANCTIONED &ITS CORRI.` (+ a longer "…& ITS CORRI." variant). Varied rows also use `DRAFT AMENDMENT SANCTIONED` and `DRAFT VARIATION SANCTIONED`.
  Mapping to the catalog: `FINAL…` → final, `PRELIMINARY…` → preliminary, `DRAFT…` → draft. Varied rows map to `sanctioned_variation`, or keep the principal status plus a variation note (this is a decision for later).
- **Current Status Date:** `dd/mm/yyyy` (e.g. `16/07/1925`, `21/10/2022`). This is the only listing in this research that has real per-scheme status dates.
- **Drawing Name cell** has junk to filter out:
  - Empty `<a>` tags with `href="file:///E:/AMC/TCS/…"` (296 of them; leftover paste from a desktop file). **Ignore any href that does not start with `/Uploads/`.**
  - The real link `<a href="/Uploads/TpInfo/<file>.pdf" target="_blank">` is **repeated 2–3 times with the same href**, because the
    drawing name text is split across anchors with `<br>`. De-duplicate the hrefs per cell, and join the anchor texts to rebuild the drawing name
    (e.g. `TPS_1_CHANDLODIYA_PRINC_FINAL_SANC_` + `01011993_UP_TO_1VF_24042018`).
  - 304 distinct `/Uploads/TpInfo/` hrefs. File names include odd ones such as `C__Users_Acer_Desktop_Final_file_DRAFT_SANC_TPS_118_SINGARVA_PRINC_DRAFT_SANC_20112013_CURRENT.dwg.pdf`,
    paths with spaces and parentheses (`D__Prop.TPS_TP_152-G_SHILAJ_… Model (1).pdf`), and one broken-looking doubled path
    `/Uploads/TpInfo//Uploads/TpInfo/TPS_5_CITY_WALL_IMPROVEMENT_2C.pdf.pdf` (**not verified** whether it resolves).
  - One relative `portal/TPS_…pdf` and one `/portal/TPS_…pdf` href (junk, ignore). One scheme has no link at all (Sr 187, SOLA 43/B).
- **Draft TP PDFs in the "City Planning" menu** (in the page header on every page, `ul#menu-header-en`): 10 items, e.g.
  `DTPS No. 157/G (Badrabad), as Submit to Govt on Date:29-10-2024 → /ViewFile/ViewFile?TYPE=FileRepository,2307`,
  `DTPS-160(PIPLAJ-LAXMIPURA-LAMBHA) PUBLISHED DT 23-01-2024 → …FileRepository,312`,
  `DTPS No.233 (Tragad) First varied … → ViewFile/ViewFile?TYPE=FileRepository,2300` (relative without a leading slash!).
  The hrefs are a mix of absolute, root-relative and relative. Status and date appear only in free text.
  (The `/Home/sitemap` page has an **older** copy of this menu with `/Images/…pdf` links. Don't use it.)

### 3.2 File headers (HEAD, verified)

| URL | Size | Last-Modified | ETag |
|---|---|---|---|
| `/Uploads/TpInfo/TPS_1_A_BODAKDEV.pdf` | 587,922 | Thu, 06 Jul 2023 11:34:06 GMT | `"0cb8bc5fdafd91:0"` |
| `/Uploads/TpInfo/TPS_30_ASARWA_NORTH.pdf` | 2,146,879 | Thu, 06 Jul 2023 12:36:08 GMT | `"0ec7706b0d91:0"` |
| `/Uploads/TpInfo/C__Users_Acer_…TPS_118_SINGARVA…CURRENT.dwg.pdf` | 7,045,838 | Fri, 07 Jul 2023 09:22:18 GMT | `"0816c86b4b0d91:0"` |
| `/Images/_CITY_PLANNING_DTPS_158_G_FATEHWADI_OKAF_SUBMIT.pdf` | 1,185,647 | Wed, 12 Jul 2023 15:29:13 GMT | `"15fd949cd5b4d91:0"` |
| `/ViewFile/ViewFile?TYPE=FileRepository,2307` | 1,829,984 | **not sent** | **not sent** (has `Content-Disposition: inline; filename=TPS 157-G BADRABAD submit 29-10-2024-Model6185.pdf`) |

### 3.3 Update frequency

TpInfo files were bulk-uploaded in July 2023. The table has status dates up to 2022 (152/G) and varied dates up to 2021. The menu has draft items dated 2024.
This looks like **infrequent** updates. The page has no "last updated" stamp.

**Verdict: YES** (the richest data source, but the scraper must handle rowspans and junk anchors). The 10 menu drafts are a partial extra.

---

## 4. Ahmedabad — AUDA

- **Base URL:** `https://www.auda.org.in` (ASP.NET WebForms, IIS 10). Links in the pages mix `http://www.auda.org.in`, `http://auda.org.in` and `https://auda.org.in`.
- **robots.txt:** 404. **TLS:** fine. **Language:** English (the site has a Gujarati toggle via postback, not used).
- **Listing:** `https://www.auda.org.in/TPScheme.aspx` (menu "TP Scheme"). One table, **94 schemes, no pagination**. Server-rendered (there is a WebForms `__VIEWSTATE`, but no postback is needed to see the data).

### 4.1 Structure (fixture `auda/tp_scheme.html`)

`table.gridtable.table.table-bordered.myTable` with columns:
`Sr. No.` | `T.P.S. No` | `Area/Village` | `Date of Sanction of Draft T.P. Scheme` | `Date of Sanction of Preliminary Scheme` | `Date of Sanction of Final Scheme` | `"F" Form`

- **Status comes from which date is filled**: final date → final, else preliminary date → preliminary, else draft date → draft. If all are empty → unknown/draft (e.g. 139/B, 139/A, 413, 417/B, 151, 307). Dates are `dd/mm/yyyy`.
- **T.P.S. No:** `419`, `139/B`, `10/A`, `440+352`, … Numbers repeat across villages (several `1`, `2`, `11`).
- **Area/Village cell** has an `<a id="Body_container_rptTPScheme_aTPS_<i>" onclick="ShowTPSchemeImage(this);">ASLALI</a>` (no href) and a hidden input
  `<input type="hidden" id="Body_container_rptTPScheme_hfImageUrl_<i>" value="/uploads/TPScheme/116.jpg" />`. **That hidden input's value is the map image URL** (root-relative JPG). The JS just opens it.
  JS treats a value of exactly `/uploads/TPScheme/` as "no image". All 94 rows have a `.jpg`.
- **F-Form cell:** `<a href="/uploads/TPScheme/116.pdf" id="Body_container_rptTPScheme_a2_<i>" target="_blank">Click Here</a>`. The numeric ID is the same as the JPG's.

### 4.2 File headers (HEAD, verified)

| URL | Size | Last-Modified | ETag |
|---|---|---|---|
| `/uploads/TPScheme/116.jpg` (map) | **14,439,310** | Sat, 02 Jul 2022 07:32:14 GMT | `"9356ded9e58dd81:0"` |
| `/uploads/TPScheme/116.pdf` (F-form) | 1,239,351 | Tue, 15 Mar 2022 11:25:46 GMT | `"7d533b6a5f38d81:0"` |

### 4.3 DP

`https://www.auda.org.in/RDP/` (fixture `auda/rdp.html`) has a list of "Click Here" links to `http://www.auda.org.in/uploads/Assets/rdp/*.pdf|jpg`
(DP 1987, DP 2002, Revised DP 2021 notifications, `audareviseddevelopmentplan2022map04112022064034976.pdf`, `Basemap-36X36.jpg`, …). Scrapable as DP documents. The labels are only "Click Here", so the description has to come from the neighbouring text (not analysed in detail).

### 4.4 Update frequency

Draft dates go up to 2022 (429 Godhavi Manipur, 08/04/2022) and the final date up to 21/12/2021. Files are from 2022. This looks **rarely updated**.

**Verdict: YES.** 94 schemes, server-rendered table with 3 date columns, map JPG + F-form PDF, good headers.

---

## 5. Vadodara — VMC

- **Base URL:** `https://vmc.gov.in` (ASP.NET, `Microsoft-IIS/8.0`). **robots.txt:** 404 (empty body). **TLS:** fine. **Language:** English.
- `DepartmentTP.aspx` ("Land & Estate (T.P.)") is only a description, with no files.
- `DraftTPSchemeMaps.aspx` ("Draft TP Scheme (EWS)") has one ZIP: `../Zip/tpdepartment.zip` ("TPS Sheme - EWS & Residential Reserve Plots"), 106,391 bytes, Last-Modified 19 Jul 2013, no ETag.
- **Listing:** `https://vmc.gov.in/TDOTP.aspx` ("Town Development Department (T.P.)").

### 5.1 Structure (fixture `vmc/tdotp.html`)

There is no table. Inside `main.main`, cards look like
`div.pricing-item > div.pricing-header h4` (group title) + `div.pricing-feature2 > ul > li > a[href]`.
Group titles (h4 text): `Draft TP` (2 cards: 16 + 17 links), `Priliminary TP` (10), `F - Form` (3), `Final TP` (3 cards: 13 + 10 + 10).
The F-Form card sits inside the same column as Priliminary, so **walk the h4s in document order** and give each following link to the nearest previous h4.

- 79 links in total. All are **relative with raw spaces**, e.g. `pdf/2022/TDOTP/Draft TP/Draft TP Scheme No.1 (Gorva-Ankodia).pdf`,
  `pdf/2022/TDOTP/Final TP/TP Scheme, Baroda NO.1 (Final).PDF` (`.pdf` and `.PDF` both occur), resolved against `https://vmc.gov.in/`.
- The **only metadata is the link text**: `Draft TP Scheme No.24 A (Ankodia-Khanpur-Sevasi-Mahapura)`, `TP Scheme No.4 (Bapod) (1st varied)`,
  `TP Scheme, Baroda No. 7 (Savad) (Final)`, `TP Scheme,Vadodara No.13 (Final)` (old "Baroda No." / "Vadodara No." series without a village name),
  `Proposed T.P-52 (Tarsali)`. Some links are not schemes: `Reservation Plots Detail (Final)`, `TP 51 Kalali Owner's Meeting`.
- No dates (the upload year folder `pdf/2022|2023|2025|2026/` is a hint).

### 5.2 File headers (HEAD, verified)

| URL | Size | Last-Modified | ETag |
|---|---|---|---|
| `pdf/2022/TDOTP/Final%20TP/TP%20Scheme%20No.1%20(Bil)%20(Final).pdf` | 227,360 | Mon, 11 Apr 2022 06:34:28 GMT | **none** |
| `pdf/2026/TDOTP/Proposed%20Draft%20T.P-52.PDF` | 741,147 | Mon, 06 Apr 2026 07:18:02 GMT | **none** |

### 5.3 Other

`https://vmap.vmc.gov.in/citizenportal/home` ("Search By Census No.", a GIS portal) was **not examined**.

**Verdict: PARTIAL.** It is scrapable (static HTML), but scheme number and area must be parsed from free link text. The numbering is mixed (village-wise vs old Baroda/Vadodara series), there are no dates and no ETag, and some links are not schemes.

---

## 6. Vadodara — VUDA

- **Base URL:** `https://www.vuda.co.in` (Apache, static `.htm`). The domain came from a web search and I **verified it by fetching**. `vuda.gujarat.gov.in` does not resolve.
- **robots.txt:** 404. **TLS:** fine. **Language:** English. **JS:** the top menu is built by a JS menu library (`stmenu.js`, `stm_aix(...)` calls in the HTML). The menu targets can be read from those calls, and the listing pages themselves are plain HTML. The sub-pages load `header.htm`/`footer.htm` via JS (`loadHTML`), which is not needed for the content.

### 6.1 Listing pages (verified)

| URL | Content | Links |
|---|---|---|
| `https://www.vuda.co.in/tp_scheme_vuda.htm` (menu "TP scheme Vuda") | Index with 4 buttons | → the 4 pages below |
| `/tp_scheme_vuda_draft.htm` | Draft | 20 PDFs (10 schemes × drawing + F-form) |
| `/tp_scheme_vuda_sanctioned_draft.htm` | Sanctioned Draft | 10 (5 schemes) |
| `/tp_scheme_vuda_priliminary.htm` | Priliminary | 6 (3 schemes) |
| `/tp_scheme_vuda_final.htm` | Final | 22 (11 schemes) |
| `/tpscheme.htm` (menu "Town planning schemes") | Legacy page with 18 TP PDFs (`download/TPSNO42(KOYALI).pdf`, `download/DTP_22_Drawing.pdf`, … drawing + "Patrak") that **overlap** with the draft page | 20 PDFs |
| `/` (home, `index.htm`) | Latest items: `download/TP3_pda.pdf` ("TP 3 MAP", Padra), `download/TP-4_map.pdf`, `download/TPS_3_PADRA_PDS_SHEET.pdf`, `download/TPS_4_PADRA_PDS_SHEET.pdf` | 4 |
| `/download_tpscheme.htm` | "Download Map Drawings for TP Scheme": **empty page** (only navigation) | 0 |

### 6.2 Structure (fixtures `vuda/tp_*.html`)

Each status page has one `<table style="width: 100%">`, with one `<tr><td><p align="center"><a target="_blank" href="…">TEXT</a></p></td></tr>` per file.
Hrefs are **relative**: `TPSchemeVuda/<status>/<scheme-folder>/<file>.pdf`, e.g.
`TPSchemeVuda/draft/TP-21-SAMIYALA-BIL/T.P.S.NO.-21.pdf` and `TPSchemeVuda/draft/TP-21-SAMIYALA-BIL/T.P.S.NO.-21-F-FORM.pdf`;
`TPSchemeVuda/final/bhayali-tp-1/BHAYALI-T-P-1.pdf`. **Group files by the `<scheme-folder>` path segment.** The status is the folder (`draft`, `sanctioned_draft`, `priliminary`, `final`).
Tell the map from the F-form by "F-FORM"/"F-Form"/"Form" in the text or filename. Scheme numbers are only in the folder or link text and are inconsistent
(`TP-24-A`, `ANKODIYA-1`, `Khanpur-Ankodiya-2`, `bhayali-tp-1`). The final page also has `PADARA-T-P-S-NO-01` and `PADRA-NO1` as separate links. No dates.

### 6.3 File headers (HEAD, verified)

| URL | Size | Last-Modified | ETag |
|---|---|---|---|
| `TPSchemeVuda/draft/TP-21-SAMIYALA-BIL/T.P.S.NO.-21.pdf` | 1,969,848 | Tue, 19 Mar 2024 11:46:40 GMT | `"1e0eb8-6140206fd0800"` |
| `download/TP-4_map.pdf` | 553,667 | Fri, 07 Aug 2026 04:51:57 GMT | `"872c3-6586dc3a03540"` |

Update frequency: the Padra TP 3/4 files on the home page are from Aug 2026, and the status pages from 2024. Occasional updates.

**Verdict: PARTIAL.** It is static and parseable, and the status comes from the page/folder. But scheme identity must be inferred from folder names, there is a duplicate legacy page, and the newest schemes (Padra 3/4) are only on the home page.

---

## 7. Rajkot — RMC

- **Main site:** `https://www.rmc.gov.in` (robots 404). Its "Town Planning" menu has only forms. The home page links **"T.P.Map" → `https://egov.rmc.gov.in/TPMAP`**.
- **Listing host:** `https://egov.rmc.gov.in` (ASP.NET WebForms; robots 404; TLS fine). **JS:** not needed. **Language:** English.

### 7.1 Structure (fixture `rmc/tpmap.html`)

There are two side-by-side tables, `table#grid` (Sr 1–34) and `table#clsgrid` (Sr 35–68). Each has columns `Sr.No.` | `Scheme`. **68 schemes.**

- Sr cell: `<span id="body_rptTPMAPMain1_Label1_0">1</span>`.
- Scheme cell: `<a id="body_rptTPMAPMain1_Label2_0" href="Masters/ViewDoc.aspx?fileName=cR%2bncXMaim4jisTTK1hdu3r63Smu44gRphGycqcK2Ck%3d&amp;TiKnA=0" target="_blank">T.P.S. NO.-1  (RAIYA) FINAL</a>`.
  **The status is the last word of the link text**: `FINAL`, `PRILI`, `DRAFT`/`Draft`. Some entries have no status (`T.P.S. NO.- 11 MADHAPAR`, `T.P.S. NO.- 44 MOTAMAVA`, `T.P.S. NO.- 46 GHANTESHWAR`).
  Text variants: `T.P.S. NO.-13 KOTHARIYA PRILI` (no parentheses), `T.P.S. NO.- 36-3 GHANTESHWAR PRILI`, `T.P.S. NO.-20+21 (MUNJAKA) DRAFT`, `TPS-26 (VAVDI) Draft`.
  Numbers repeat across areas (TPS 1 Raiya / TPS 1 Rajkot), and one row repeats the exact text `T.P.S. NO.-4 (RAJKOT) FINAL` twice with different tokens.
- 65 rows link to `Masters/ViewDoc.aspx?fileName=<encrypted token>&TiKnA=0` (relative, resolves to `https://egov.rmc.gov.in/Masters/ViewDoc.aspx?...`).
  The token is **opaque** (the file name is encrypted). It was **identical across two fetches minutes apart**. Stability over days/weeks is **not verified**, so do not use the URL as an identity.
- 3 rows (Sr 60–62) link to a detail page `/TpMapPlans?tpid=60|61|62`. That page (fixture `rmc/tpmapplans_tpid60.html`) has the same 2-column table with several ViewDoc links (tpid=60: "MADHAPAR" map + "F FORM").

### 7.2 File headers (HEAD, verified)

`HEAD https://egov.rmc.gov.in/Masters/ViewDoc.aspx?fileName=cR%2bncXMaim4jisTTK1hdu3r63Smu44gRphGycqcK2Ck%3d&TiKnA=0` returns
200, `Content-Type: Application/pdf`, `Content-Length: 7992816`, **no ETag, no Last-Modified, no Content-Disposition**. It sets an `ASP.NET_SessionId` cookie and `AuthToken=`.
So change detection can only use Content-Length (or a periodic re-hash).

Update frequency: unknown (no dates anywhere).

**Verdict: PARTIAL.** The list of 68 schemes with status is easy to parse. But there is only one PDF per scheme, encrypted file URLs, no dates, and only Content-Length to detect changes.

---

## 8. Rajkot — RUDA

- **Base URL:** `https://rajkotuda.com` (IIS 10, static HTML). The domain came from a web search and I **verified it by fetching**. **robots.txt:** 404 (empty). **TLS:** fine. **Language:** English.
- **Listing:** `https://rajkotuda.com/town-planning-scheme.html` (Town Planning Department → Town Planning Scheme). **11 schemes**, no pagination.

### 8.1 Structure (fixture `ruda/town_planning_scheme.html`)

`table.table.table-bordered.table-striped.table-condensed.tbl2`. There is no thead; the first `<tr>` has the `<th>`s:
`Sr. No.` | `T.P.S. NO.` | `Area/village` | `Date of sanction of draft` | `Date of sanction oF Priliminary scheme` | `Date of sanction of Final Scheme` | `Submitted to Govt. for Draft Approval` | `Plan` | `F forms`

- Dates are `dd/mm/yyyy`, or `-` when empty. Status comes from the latest filled date: final > preliminary > draft > submitted.
  Example: `43 | VAJDI VAD | 01/11/2018 | 26/09/2025 | - | -` = preliminary. `53 | Khokhadadad | - | - | - | 11/09/2026` = submitted (draft, not sanctioned).
- T.P.S. NO.: `43`, `41`, `38/2`, `77`, `80`, `81`, `82`, `53`, `54`, `55`, `57`.
- Plan / F forms: `<a href="pdf/tp/TP-43/43_VAJDI_VAD_PLAN.pdf" target="_blank">Plan</a>`, `uploads/T.P.41 plan no.3.pdf` (relative, can contain spaces), resolved against `https://rajkotuda.com/`.
- Only recent schemes are listed. RUDA's older schemes are **not on this page**.

### 8.2 File headers (HEAD, verified)

| URL | Size | Last-Modified | ETag |
|---|---|---|---|
| `pdf/tp/TP-43/43_VAJDI_VAD_PLAN.pdf` | 978,658 | Mon, 13 Jul 2026 10:16:38 GMT | `"3d9c3fb1b012dd1:0"` |
| `uploads/TPS_53_PLAN_3.pdf` | 940,304 | Wed, 16 Sep 2026 05:51:00 GMT | `"bf2945a9f45dd1:0"` |

### 8.3 DP

`https://rajkotuda.com/development-plans-download.html` (fixture `ruda/development_plans_download.html`) has links to `pdf/proposed-dp-1988.pdf`, `pdf/index-2004.pdf`, `pdf/dp2031/dp.pdf`, `pdf/Existing-Land-Use-2012.pdf`. The anchors have **no text** (image links). The same page also has unrelated tender PDFs.

Update frequency: dates up to 11/09/2026 and files from Jul/Sep 2026. **Actively updated.**

**Verdict: YES** (small but clean, with dates).

---

## 9. State — townplanning.gujarat.gov.in (TPVD)

- **Base URL:** `https://townplanning.gujarat.gov.in` (redirects to `/Home`; ASP.NET Core). **robots.txt:** 404 (empty). **TLS:** fine. **Language:** English, with Gujarati descriptions in some rows.
- `/Townplanningscheme` and `/Developmentplan` contain **only explanatory text**, with no lists or files. `/DPIFC` is a facilitation-cell page (one order PDF).
- The "TP WebGIS" link goes to `https://tpvd.openprp.in/pro/main/modules/role_public/map/index.php`. From here, **the connection to tpvd.openprp.in:443 failed** (could not connect). Not examined.

### 9.1 Notifications (fixture `tpvd/ecitizen_notifications.html`)

`https://townplanning.gujarat.gov.in/ecitizen/Notifications` has one table, with `tbody#documentRows`. **107 rows**, footer "Page 1 of 1" (the pagination buttons are client-side; all rows are in the HTML).
Columns: `Date` (dd-mm-yyyy) | `Category` (badge "Notifications") | `Subject` (`L Branch`, `CGDCR`) | `Title` | `Reference No.` | `Description` | `Action`.
Action cell: `<a href="/FetchFile?guid=<uuid>&amp;filename=<title>.pdf" class="download-btn">` (root-relative, raw spaces in filename).
Titles name TP schemes and DPs statewide, e.g. "Notification Related to FInal Town Planning Scheme No 54 (Bhestan)",
"Notification Related to Preliminary town Planning Scheme No 30 (Asarva-North-Extension) (4th Varied)", and many "Modification in Final Development Plan of …".
The rows are **not sorted by date** (they look sorted by the dd-mm-yyyy string). Dates: 2023 ×8, 2024 ×51, 2025 ×47, 2026 ×1 (latest 15-06-2026).
`HEAD` on a `/FetchFile` URL returns **405 Method Not Allowed** (`Server: XXXXXXXXXXXXXXXXXXX`), so change checks need GET (or a `Range: bytes=0-0` GET, which is not tested).

**Verdict: PARTIAL.** There are no TP scheme maps or a scheme list. The notifications table is a clean, statewide feed of sanction notifications (useful as `files[].kind = notification` and as a "status changed" signal). Matching a row to a catalog scheme needs fuzzy title parsing.

---

## Catalog impact (please review before Milestone 2)

1. **`id = {city_id}-{type}-{scheme_no}` (PLAN §5) will collide.** Within one authority, the same number is reused for different villages
   (SMC TP 1 ×3, AMC "1" ×15, RMC TPS 1 Raiya/Rajkot, AUDA "1" ×6). Across authorities in the same city it also collides (SMC and SUDA both have TP 86).
   Suggestion: include authority and area, e.g. `surat-smc-tp-1-vesu`. That needs a decision and a `docs/decisions.md` entry.
2. **Status mapping** differs per source: an explicit table (SMC, SUDA, VUDA folders, VMC headings), text values (AMC), date columns (AUDA, RUDA), or a link-text suffix (RMC).
   "Submitted to Govt." (SMC section 4, SUDA, RUDA) has no enum value. Map it to `draft` with a note, or add an enum value.
3. **Change detection:** SMC ETags are timestamp-based and not unique. VMC has no ETag. RMC and AMC `/ViewFile` send only Content-Length. TPVD rejects HEAD.
4. **Large files:** SUDA has a 57 MB plan PDF, and AUDA map JPGs are about 14 MB.
5. **URL hygiene the scraper must do:** percent-encode spaces in hrefs (SMC, VMC, RUDA, AMC, TPVD); turn backslashes into slashes (SMC notifications);
   drop `file:///` and `portal/` hrefs and de-duplicate repeated anchors (AMC); handle relative links without a leading slash (AMC menu, VMC, VUDA, RUDA, RMC).

## Fixture files (all fetched 2026-11-08)

All paths are relative to `pipeline/fixtures/`.

| Fixture | Source URL |
|---|---|
| `smc/tp_all_schemes.html` | https://www.suratmunicipal.gov.in/Departments/TownPlanningAllTPSchemes |
| `smc/tp_details.html` | https://www.suratmunicipal.gov.in/Departments/TownPlanningTPDetails |
| `smc/tp_final.html` | https://www.suratmunicipal.gov.in/Departments/TownPlanningSanctionedFinalSchemes |
| `smc/tp_preliminary.html` | https://www.suratmunicipal.gov.in/Departments/TownPlanningPreliminarySchemes |
| `smc/tp_draft.html` | https://www.suratmunicipal.gov.in/Departments/TownPlanningDraftSchemes |
| `smc/tp_draft_submitted.html` | https://www.suratmunicipal.gov.in/Departments/TownPlanningDraftSchemesSubmitToGov |
| `smc/notifications_TP01_Udhna-Majura.html` | https://www.suratmunicipal.gov.in/notifications/Notifications?Id=TP01%20Udhna-Majura |
| `smc/notifications_TP94_MOTA_VARACHHA.html` | https://www.suratmunicipal.gov.in/notifications/Notifications?Id=TP94_MOTA_VARACHHA |
| `smc/dp_sheets.html` | https://www.suratmunicipal.gov.in/Departments/TownPlanningDevelopmentPlans |
| `suda/tp_sanctioned.html` | https://www.sudaonline.org/services/tp-schemes/ |
| `suda/tp_submitted_to_govt.html` | https://www.sudaonline.org/submitted-to-govt-tp-scheme/ |
| `suda/tp_published.html` | https://www.sudaonline.org/services/published-tp-scheme/ |
| `suda/tp_intention.html` | https://www.sudaonline.org/services/tp-scheme-intention/ |
| `suda/dp2035_sheets.html` | https://www.sudaonline.org/development-plans/dp-2035-sheet-dt-08-10-2020-corrigendum-9-11-2020/ |
| `amc/tp_scheme_information.html` | https://ahmedabadcity.gov.in/SP/TPSchemeInformation |
| `auda/tp_scheme.html` | https://www.auda.org.in/TPScheme.aspx |
| `auda/rdp.html` | https://www.auda.org.in/RDP/ |
| `vmc/tdotp.html` | https://vmc.gov.in/TDOTP.aspx |
| `vmc/draft_tp_scheme_maps_ews.html` | https://vmc.gov.in/DraftTPSchemeMaps.aspx |
| `vuda/tp_scheme_vuda.html` | https://www.vuda.co.in/tp_scheme_vuda.htm |
| `vuda/tp_draft.html` | https://www.vuda.co.in/tp_scheme_vuda_draft.htm |
| `vuda/tp_sanctioned_draft.html` | https://www.vuda.co.in/tp_scheme_vuda_sanctioned_draft.htm |
| `vuda/tp_preliminary.html` | https://www.vuda.co.in/tp_scheme_vuda_priliminary.htm |
| `vuda/tp_final.html` | https://www.vuda.co.in/tp_scheme_vuda_final.htm |
| `vuda/tpscheme_legacy.html` | https://www.vuda.co.in/tpscheme.htm |
| `vuda/home.html` | https://www.vuda.co.in/ |
| `rmc/tpmap.html` | https://egov.rmc.gov.in/TPMAP |
| `rmc/tpmapplans_tpid60.html` | https://egov.rmc.gov.in/TpMapPlans?tpid=60 |
| `ruda/town_planning_scheme.html` | https://rajkotuda.com/town-planning-scheme.html |
| `ruda/development_plans_download.html` | https://rajkotuda.com/development-plans-download.html |
| `tpvd/ecitizen_notifications.html` | https://townplanning.gujarat.gov.in/ecitizen/Notifications |
| `tpvd/townplanningscheme.html` | https://townplanning.gujarat.gov.in/Townplanningscheme |
| `tpvd/home.html` | https://townplanning.gujarat.gov.in/ (→ /Home) |

**Git note:** `.gitattributes` has `* text=auto eol=lf`, so git will convert these CRLF fixtures to LF on commit.
That doesn't affect parsing. If byte-exact fixtures matter, add `pipeline/fixtures/** -text` to `.gitattributes`. That has **not** been changed.

## Not verified / not examined

- `https://gis.suratmunicipal.org/` (SMC GIS), `https://vmap.vmc.gov.in/citizenportal/home` (VMC GIS), and `https://tpvd.openprp.in/…` (state TP WebGIS; connection failed from here).
- AMC doubled path `/Uploads/TpInfo//Uploads/TpInfo/TPS_5_CITY_WALL_IMPROVEMENT_2C.pdf.pdf`: not tested.
- Whether RMC ViewDoc tokens stay the same over days.
- SUDA "Published TP Scheme" and "TP Scheme Intention" pages currently show no entries. Their structure when filled is unknown.
- Older RUDA TP schemes (pre-2018) are not on RUDA's site as far as I found.

## Addendum (2026-11-08, first live pipeline run)

- **AMC (ahmedabadcity.gov.in) TLS:** curl on Windows (Schannel) fetched it fine. Python/OpenSSL 3
  failed twice:
  1. The server needs **TLS legacy renegotiation**, which OpenSSL 3 disables by default.
  2. It sends an **incomplete chain**: the intermediate "Sectigo Public Server Authentication CA
     OV R36" is missing.

  The AMC scraper lists the host in `legacy_tls_hosts`. The PoliteClient then allows legacy
  renegotiation and adds the bundled intermediate from `pipeline/opennaksha/certs/`, downloaded
  from the AIA URL in the server certificate. **Certificate verification stays on.**
- **Live results with `--no-download`:** SMC 146, SUDA 33, AMC 272, AUDA 94, RUDA 11, VUDA 28
  schemes. A second run against the first reported zero changes.

---

## Non-TP maps: DP, LAP, village (researched 2026-11-09)

The rules are the same as above. Every URL, count and header below was fetched on **2026-11-09**
with the same User-Agent, at least 1.1 s between requests to a host, and a 30 s timeout. Files were
checked with `HEAD` only. Anything not fetched is marked **not verified**. Robots.txt was re-checked:
sudaonline.org still only disallows `/wp-admin/`. auda.org.in, rajkotuda.com, guda.gujarat.gov.in
and vuda.co.in have none (404). Nothing used below is disallowed.

### Summary

| Source | What | Listing URL | Files | JS? | Validators (HEAD) | Verdict |
|---|---|---|---|---|---|---|
| **SUDA** | Sanctioned DP-2035 sheets (46 + index map) | `/development-plans/dp-2035-sheet-dt-08-10-2020-corrigendum-9-11-2020/` | JPG 8400 px, 0.2–0.7 MB | No | **Content-Length only** (JPGs send no ETag/LM) | **yes** |
| **SUDA** | DP-2035 variations (11 notifications, villages named) | `/development-plans/sanction-dp-2035-proposed-variation/` | PDF, 1.7–69 MB | No | ETag + LM + CL | **yes** |
| **SUDA** | Old DPs: 2004 (27 sheets) and 1986 (20 sheets) | `/development-plans/development-plan-2004/`, `…-1986/` | JPG, max 1000 px (low-res) | No | CL only | **partial** (low resolution) |
| **SUDA** | Draft DP-2035 sheet sets (2016, 2017 u/s 16, 2019 "online data") | 3 gallery pages (see 10.1 d) | JPG 3000–4800 px | No | CL only | **partial** (superseded drafts) |
| **AUDA** | DP 1987 / 2002 / 2021 / 2022 maps, plus notifications and GDCR | `https://www.auda.org.in/RDP/` | PDF/JPG, up to **323 MB** | No | ETag + LM + CL | **yes** (4 map rows) |
| **RUDA** | DP 1988 / 2004 / 2031 / existing 2012, plus 3 grid sets of 29 sheets | `https://rajkotuda.com/development-plans.html` (+3 grid pages) | PDF, 1–113 MB | No (HTML image map) | ETag + LM + CL | **yes** |
| **VUDA** | **DP village maps** (2nd revised DP, 123 villages, 208 PDFs) | `https://www.vuda.co.in/dpvillagemaps.htm` | PDF 0.8–2.3 MB | No | ETag + LM + CL | **yes** |
| **GUDA** (new host) | First Revised DP-2024: 35 sheets + key map + full plan | `https://guda.gujarat.gov.in/resources.htm` | PDF 2.5–20 MB | No | ETag + LM + CL | **yes** |
| **SMC** | Old DP sheets A–Z (villages listed per sheet) | `/Departments/TownPlanningDevelopmentPlans` | **ZIP only** (1.6 MB sample) | No | ETag + LM + CL | **partial** (ZIP-only, the app can't show these) |
| **VMC** | 3 city-wide map files (no DP) | `https://vmc.gov.in/TDO.aspx` | ZIP 84 MB, PDF 49 MB, PDF 4.5 MB | No | LM + CL, no ETag | **no** for DP (optional "other") |
| **RMC** | Nothing (RMC's area is in RUDA's DP) | – | – | – | – | **no** |
| **AMC** | Nothing found (AMC's area is in AUDA's DP) | – | – | – | – | **no** |
| **TPVD** | No DP list or maps. 39 of 107 notification rows are DP modifications/variations | `/ecitizen/Notifications` (see §9.1) | PDF via `/FetchFile` | No | HEAD → 405 | **partial** (notifications only) |
| **LAPs** (all of the above) | **No published Local Area Plan map found anywhere** | – | – | – | – | **no** |
| **Village boundary / gamtal maps** | Only VUDA's DP village maps. Village *lists* (no maps) at SUDA, RUDA, AUDA. Revenue village maps are on AnyROR (link-out only) | – | – | – | – | see 10.9 |

### 10.1 Surat — SUDA (sudaonline.org, WordPress)

**DP index:** `https://www.sudaonline.org/development-plans/` (fixture `suda/dp_index.html`). Its `div.entry-content` has 6 links:
- the DP-2035 sheet gallery;
- a PDF, `wp-content/uploads/2020/11/SANCTION-MODIFICATION-DP-2035-NOTIFICATION-DT-08-10-2020-CORRIGENDUM-DT-09-11-2020.pdf` (the sanction notification);
- `development-plan-2035/`;
- `/rdp-2035/` (2013 workshop text and one presentation PDF, no maps);
- `development-plan-2004/`;
- `development-plan-1986/`.

The site menu also has "Sanction DP – 2035 Proposed Variation" and "SUDA Authority Map".

**a) Sanctioned DP-2035 sheets** (fixture `suda/dp2035_sheets.html`; re-fetched today, links unchanged)
- `h1.entry-title` (Gujarati): "સુડા–મંજુર વિકાસ યોજના -૨૦૩૫ નકશા – જાહેરનામા ક્રમાંક : GH/V/157 of 2020/DVP-142018-5731-L Date-08/10/2020 તથા Corrigendum No. GH/V/173 of 2020/DVP-142018-5731-L Date – 09/11/2020."
- **Index map:** the first `<p><a href=".../2020/11/INDAX-MAP.jpg">` in `entry-content`, before the gallery (8400×8400, 544,885 bytes).
- **Sheets:** `div#gallery-1 dl.gallery-item` (46 items). In each item:
  - `dt.gallery-icon > a[href]` is the full JPG, absolute: `https://www.sudaonline.org/wp-content/uploads/2020/11/<ID>.jpg`.
  - `a[data-lbwps-caption]` and `dd.gallery-caption` give the sheet id.
  - `data-lbwps-width/height` give the size in pixels.
- **Sheet ids, in order:** `BASE MAP` (file `BASE-MAP.jpg`), `A`, `B`, `C`, `C1`, `D`, `D1`, `E`, `E1`, `F`, `F1`, `G`, `H`, `H1`, `I`, `J`, `J1`, `K`, `K1`, `L`, `L1`, `M`, `M1`, `N`, `N1`, `O`, `O1`, `P`, `P1`, `Q`, `Q1`, `R`, `R1`, `S`, `S1`, `T`, `T1`, `U`, `U1`, `V`, `V1`, `W`, `W1`, `X`, `Y`, `Z`.
- **Widths:** 8400 px, except G 6300, P 8327, Q 8320 and BASE MAP 8422.
- **HEAD:** `A.jpg` 606,148 B, `BASE-MAP.jpg` 733,786 B, `Z.jpg` 234,344 B, all `image/jpeg`. **No ETag and no Last-Modified** (PDFs on the same host send both). So change detection is Content-Length plus a periodic re-hash.
- The page gives no village names per sheet. The index map image is the only key.

**b) DP-2035 variations:** `https://www.sudaonline.org/development-plans/sanction-dp-2035-proposed-variation/` (fixture `suda/dp2035_variations.html`)
- **Title** (Gujarati): "સુડા મંજુર વિકાસ યોજના – ૨૦૩૫ નાં સૂચિત ફેરફારો અંગેની વિગતો" ("details of proposed changes to the sanctioned DP-2035"). File names contain `us-19` or `Proposed-Variation_us-19`.
- `div.entry-content` holds **11 groups separated by `<hr>`**. Each group has:
  1. **Number and date:** `<p>(૧) સુડાની મંજુર વિકાસ યોજના – ૨૦૩૫ અન્વયે … તારીખ: ૦૯/૦૭/૨૦૨૪ નાં જાહેરનામાં બાબત.</p>`. The date is in **Gujarati digits** (convert ૦–૯).
     - Group 10 has two dates ("૧૧/૦૯/૨૦૨૫ તથા ૨૬/૦૯/૨૦૨૫").
     - Group 7 uses an ASCII "(7)".
  2. **Villages:** `<p>મોજે : સોનારી(SMC), અબ્રામા(SMC), ખરવાસા, …</p>`. **Village names in Gujarati**, comma-separated, sometimes joined with "અને" ("and"), with `(SMC)` suffixes and an en-dash entity. **Group 8 has no મોજે line**; it covers sheets 2–22.
  3. **Files:** a `table.table.table-bordered.table-customized`. Each row is `td` (૧)/(૨)/(૩) | label | `a.no-cache[href]` "↓ Download". Labels map to file kinds:

     | Label | Meaning | Kind |
     |---|---|---|
     | `રાજ્ય-પત્રમાં પ્રસિદ્ધિની વિગત` | gazette publication | notification |
     | `જાહેરનામાં ક્રમાંક: GH/V/113 of 2024/…` | notification number | notification |
     | `જાહેરનામાંને સંલગ્ન નકશા` / `જાહેરનામાને સંલગ્ન નકશા` | maps attached to the notification | **map** |

     In group 8, the map label row has **no link**. It is followed by 3 rows (`શીટ નંબર ૨ થી ૮`, `૯ થી ૧૫`, `૧૬ થી ૨૨`) that link the map PDFs.
- **Links:** 33 in total, absolute `wp-content/uploads/YYYY/MM/…pdf` (2024/08 to 2026/03). Notification dates run from 09/07/2024 to 27/02/2026.
- **HEAD** (all `application/pdf` with ETag + LM + CL):
  - `2024/08/3.-Maps.pdf`: **69,354,689 B**, LM 14 Aug 2024, ETag `"42244c1-66bca79c-…;;;"`.
  - `2025/05/3.Sheet-No-2-to-8.pdf`: 46,669,512 B.
  - `2026/03/Dt.27-02-2026_-MAP.pdf`: 1,753,325 B.

**c) DP 2004 and DP 1986** (fixtures `suda/dp2004_sheets.html`, `suda/dp1986_sheets.html`). Same `dl.gallery-item` markup.
- **2004:** 27 items, captions `Landuse`, `A` … `Z`. Files `wp-content/uploads/2013/08/landuse.jpg`, `a.jpg` … `z.jpg` (**lowercase**).
- **1986:** 20 items, captions `A`–`N`, `Q`, `U`, `V`, `X`, `Y`, `Z`. Files `2013/08/A.jpg` … (**uppercase**), and `Q-1986.jpg` for Q.
- **The server is case-sensitive:** `2013/08/A.jpg` (1986) is 156,591 B and `2013/08/a.jpg` (2004) is 137,365 B. Don't lowercase URLs.
- **Low resolution:** `data-lbwps-width` is at most 1000 px. Viewable, but barely useful as maps.

**d) Draft DP-2035 sheet sets** (all `dl.gallery-item` galleries, JPG, Content-Length only)

| Page | Fixture | Items | Upload folder | Width |
|---|---|---|---|---|
| `/development-plans/proposed-land-use-plan-submitted-us-16/` (linked from `development-plan-2035/` as "Proposed Land-use Plan Submitted U/S 16") | `suda/dp2035_proposed_us16_sheets.html` | 39 (`DP 2035` overall + `A`…`Z` with "1" suffixes) + `PROPOSAL_INDEX_MAP.jpg` | 2017/04 | 3000 |
| `/development-plans/proposed-land-use-plans/` (only in `wp-sitemap-posts-page-1.xml`, not in the menu) | `suda/dp2035_proposed_2016_sheets.html` | 52 (`RDP 2035` + `A`, `A1` … `Z`) + `INDEX_PROPOSAL.jpg` | 2016/05 | 3000 |
| `/online-data-dp-sheet-2035/` (title "ONLINE DATA DP SHEET 2035"; sitemap only; no text) | `suda/dp2035_online_data_sheets.html` | 46 (`INDEX-MAP`, `A`, `B`, `C`, `C-1` …) | 2019/02 | 4000–4800 |

- **HEAD samples:** `2017/04/A.jpg` 540,627 B; `2016/05/A.jpg` 1,031,784 B; `2019/02/A.jpg` 597,165 B.
- The pages **do not say** which planning stage the 2016 and 2019 sets belong to.
- `development-plan-2035/` (fixture `suda/dp2035_page.html`) also links:
  - "Section 13 Notifications" (`2016/05/Full-page-photo.pdf`);
  - GDCR-2016;
  - "DDP 2035 - Draft Report Submitted U/S 16" (10 report PDFs in 2017/03 and 2025/06; text, not maps).

**e) Authority map and village list**
- `/suda-authority-map/` (fixture `suda/authority_map.html`): one PDF, `2013/08/SUDA-AUTHORITY-9_12_2015.pdf` (105,504 B, LM 30 Dec 2015, ETag), and a 1000 px JPG.
- `/village-list/` (fixture `suda/village_list.html`): **text only**. Village names grouped under "Taluka Chorasi :", "Taluka Kamrej :", … No maps.

**Not found on SUDA:** any LAP page (none in the page or post sitemaps) and any village-wise DP sheets.

### 10.2 Ahmedabad — AUDA `/RDP/`

`https://www.auda.org.in/RDP/` (fixture `auda/rdp.html`; re-fetched today, links identical). Menu path: Planning → "Revised development Plan 2021".

- **Header:** `span#Body_container_lblHeader` = "Revised Development Plan 2021".
- **Table:** one `table.gridtable`. Its `thead` is `Sr. No.` | `Title` | `View Detail`.
- **Rows:** each `tbody tr` has three cells:
  1. `td span.name` (Sr. No.);
  2. `td span.name` (the **title**; trim whitespace), plus an optional `img.imgnew` ("New" GIF);
  3. `td a[href]` with the text "Click Here".
- **Links:** absolute `http://www.auda.org.in/uploads/Assets/rdp/<file>` with raw spaces. They **301 to https**.

| # | Title (from the page) | File | Kind |
|---|---|---|---|
| 1 | Thol Eco Sensetive Zone Gazzate - Draft | `Thol Eco Sensetive Zone Gazzate - Draft.pdf` | notification |
| 2 | DP-Corrigendum | `DP-Corrigendum.pdf` | notification |
| 3 | Gazette(10-06-13) | `Gazette(10-06-13).pdf` | notification |
| 4 | Note on Revised Development Plan 2021 | `Note on Revised Development Plan 2021.pdf` | other |
| 5 | Affordable Housing | `affordable housing.pdf` | other |
| 6 | **AUDA REVISED DEVELOPMENT PLAN 2021 MAP** | `Basemap-36X36.jpg` (52,872,200 B, LM 17 Jul 2014) | **map** |
| 7 | Govt Notification 04.03.2014 section 17 | `Govt Notification 04.03.2014 section 17.pdf` | notification |
| 8 | Gujarat Nagar Rachna Adhiniyam 1976 Act under Sec..26, 27, 28 & 49 Dt.24.02.15 | href is **truncated** at the comma (`…Sec..26, 27,`) and returns **404** | broken |
| 9 | Notication of AUDA Sanctioned Revised Development Plan | `….pdf` (5,410,350 B) | notification |
| 10 | **AUDA REVISED DEVELOPMENT PLAN 1987 MAP** | `audadp-198702062016045328297.pdf` (19,987,993 B, LM 6 Feb 2016) | **map** |
| 11 | **AUDA REVISED DEVELOPMENT PLAN 2002 MAP** | `audadp-200202062016045351027.pdf` (9,050,210 B) | **map** |
| 12–16 | Final Comprehensive GDCR-2017 (+ its notification), COMMON GDCR PART1–3 | `finalcomprehensi….pdf`, `test0214….pdf` | other |
| 17 | **AUDA REVISED DEVELOPMENT PLAN 2022 MAP** | `audareviseddevelopmentplan2022map04112022064034976.pdf` (**323,303,204 B = 323 MB**, LM 21 Mar 2022) | **map** |

- **HEAD:** all files send ETag + Last-Modified + Content-Length.
- **Size warning:** the 2022 map is **323 MB** and the 2021 base map JPG is **53 MB**. Both are too big to hash weekly or to open on a phone. Store metadata from HEAD only and show the size in the app.
- **Other AUDA pages checked:**
  - `/Content/development-46`: a text table of 45 draft TP schemes under preparation (no maps, no LAP files).
  - `/LC/` (Downloads): forms and lists only.
  - The "Village" menu item is a PDF, `uploads/Assets/projects/audavillages09232015060038738.pdf` (49,294 B, LM 23 Sep 2015). Its content (probably a village list) was **not opened**.

### 10.3 Rajkot — RUDA

**Main DP page:** `https://rajkotuda.com/development-plans.html` (fixture `ruda/development_plans.html`; menu Town Planning Department → Development Plans).

After the explanatory text, a `ul.bullet3` has nested `<li>`s. The top-level text gives the **plan name/year**, and the nested `<a>` text gives the **file kind**:

| Plan (li text) | Link text | href (relative to `https://rajkotuda.com/`) | Size / LM |
|---|---|---|---|
| Development Plan 1988 | (same) | `pdf/proposed-dp-1988.pdf` | **112,792,229 B**, 7 Jun 2019 |
| Development Plans 2004 | Development Plans | `pdf/index-2004.pdf` | 5,767,407 B |
| | Land Use | `pdf/land-use-2004.pdf` | 29,259 B (probably a table) |
| Development Plan 2031 (an HTML comment `<!--Proposed-->` sits before the text) | Development Plans | `pdf/dp2031/dp.pdf` | 13,593,880 B, 12 Jan 2021 |
| | Land Use | `pdf/land-use2031.pdf` | 22,778 B |
| | Grid wise existing devlopment plan | `devlopment-plan-2031.html` | (page) |
| Existing Development Plans 2012 | Land Use | `pdf/Existing-Land-Use-2012.pdf` | 22,298,340 B |
| | Grid wise existing devlopment plan | `grid-wise-existing-devlopment-plan.html` | (page) |
| | Grid wise existing land use plan | `grid-wise-existing-land-use-plan.html` | (page) |

- **HEAD:** all PDFs send ETag + LM + CL (IIS).
- **Older page:** `development-plans-download.html` (fixture `ruda/development_plans_download.html`, unchanged today) has the same 4 main PDFs in `table.tbl1`. Each row is `<td>label</td><td><a>Download</a></td>`.
- **Correction to §8.3:** the anchors there do have labels, in the first cell: "Development Plan 1988", "Development Plans 2004", "Development Plan 2031", "Existing Development Plans 2012". The tender links on that page are inside HTML comments.

**Grid sheet pages** (fixtures `ruda/dp2031_grid_sheets.html`, `ruda/existing_dp2012_grid_sheets.html`, `ruda/existing_lu2012_grid_sheets.html`)
- Each page is `div.cont-in h1` + `<img src="images/…jpg" usemap="#Map">` + `<map name="Map">` with **29 `<area shape="rect" coords="…" href="pdf/…">`**. There is no link text.
- The sheet id is the file stem. The `coords` give each sheet's position on the index image.

| Page (h1) | Index image | Sheet hrefs | Sample HEAD |
|---|---|---|---|
| `devlopment-plan-2031.html` ("Grid wise existing devlopment plan") | `images/devlopment-plan-2031.jpg` (955,174 B) | `pdf/Existing-Land-use-2031-Index-Plan/01.pdf` … `29.pdf` | 01: 5,077,792 B, LM 15 Jun 2016 |
| `grid-wise-existing-devlopment-plan.html` | `images/Existing-Land-use-2012-Index-Plan.jpg` | `pdf/Existing-Land-use-2012-Index-Plan/E-01.pdf` … `E-29.pdf` | E-01: 4,191,744 B |
| `grid-wise-existing-land-use-plan.html` ("Grid wise existing Land Use plan") | `images/Existing-Land-use-2012-Index-Plan2-2.jpg` | `pdf/development-plan-2031/1.pdf` … `29.pdf` | 1: 2,372,988 B; 29: 1,110,629 B |

**Warning: the labels look swapped.**
- The page listed under "Development Plan 2031" links to the folder `Existing-Land-use-2031-Index-Plan`.
- The page labelled "existing land use plan" (under Existing 2012) links to the folder `development-plan-2031`.

Which set is the proposed DP-2031 is **not verified** (that would need opening a PDF). The scraper should record both the page label and the folder name.

**Village list:** `village-list.html` (fixture `ruda/village_list.html`)
- An HTML table of **48 villages**: Name, Area (ha), Taluka, population 1981–2011.
- `pdf/village-list.pdf` (47,675 B).
- `images/village-list.jpg` (1,569,928 B). Its `title` attribute says "Organization Chart", so its content is **not verified**.
- No village maps.

### 10.4 Vadodara — VUDA DP village maps (best village source found)

These pages were found through the JS menu (`stm_aix(...)` calls in `vuda/home.html`): "Maps & GDCR" → "DP Maps" (`dpmaps.htm`) and "DP Village Maps" (`dpvillagemaps.htm`).

**`https://www.vuda.co.in/dpvillagemaps.htm`** (fixture `vuda/dp_village_maps.html`, 51 KB, static)
- **Heading:** `h3.decorative-heading` "DP VILLAGE MAPS Under SECTION 17", with `span.small-text` "(2nd Revised Development Plan 18-01-2012)".
- **Table:** one `table.styled-table` with `thead` `Sr.No` | `Name` | `Download Map`. **123 villages and 208 links**, all `.pdf`, all `a.pdf-link`.
- **Rowspan:** a village with several sheets has **`rowspan`** on Sr.No and Name. The continuation `<tr>`s have a single `<td>` with the link. This needs the same rowspan expander as AMC.
- **Links:** **relative, with raw spaces**: `download/DP MAPS/<FOLDER>/<file>.pdf`. Examples:
  - `download/DP MAPS/AAMLIYARA/V95.AAMLIYARA.pdf`
  - `download/DP MAPS/AKOTA/TP-1 .pdf` (a space before `.pdf`)
  - `download/DP MAPS/AJOD/AJOD .pdf`

  Encode spaces as `%20` (verified).
- **Village name:** take it from the Name cell (e.g. `AAMALIYARA`). The folder spelling sometimes differs (`AAMLIYARA`), so don't use the folder.
- **Sheet label:** the link text. Examples: `V95 AAMALIYARA`, `V144`, `ANGHADH-1`…`-4`, `TP-1`, `TP-20`, `BIL-T.P.-1`, `V29 AKOTA.pdf` (some texts include ".pdf"), `KHANPUR-ANKODIYA NO.2`.
  - The `V<number>` prefix looks like a sheet number, but the page **does not say** what it means.
  - Some villages have `TP-n` sheets.
- **Multi-sheet examples:** HARNI (V102–V106), ASOJ (V292–V294), BAPOD (TP-4, V113, V114).
- **HEAD** (all ETag + LM + CL, Apache):
  - `AAMLIYARA/V95.AAMLIYARA.pdf`: 1,393,291 B, LM 4 Apr 2012.
  - `AKOTA/TP-1%20.pdf`: 813,098 B.
  - `HARNI/V102%20HARNI.1.pdf`: 1,684,877 B.
  - `BHAYALI/BHAYALI-1.pdf`: 2,315,804 B.

  All are from **April 2012** and have not changed since.

**Other VUDA pages**
- `dpmaps.htm` (fixture `vuda/dp_maps.html`): only 3 inline 500 px images, "Proposed 1980 model", "Proposed 1996 model" and "Proposed 2004 model". Not worth scraping.
- `development.htm` (fixture `vuda/development.html`): a text history with no map files.
  - 1st DP sanctioned 22-12-83.
  - 1st revised DP 2011 notified 25-10-96.
  - 2nd revised draft DP-2031 submitted u/s 16 on 21-11-2007.
- **No VUDA DP-2031 sheet set was found**, apart from the village maps above.

### 10.5 Gandhinagar — GUDA (new host)

- **Base URL:** `https://guda.gujarat.gov.in/` (static `.htm`, IIS).
  - Found through a web-search citation of `www.guda.gujarat.gov.in`. That `www.` host 301s to https and then **fails TLS** (certificate name mismatch). The bare host works.
- **robots.txt:** 404.
- **Home page text:** "Draft Development Plan of GUDA and General Development Construction Regulations for GUDA were sanctioned by GOG on 16-2-2004 … 39 villages … 388 sq km".

**Downloads:** `https://guda.gujarat.gov.in/resources.htm` (fixture `guda/downloads.html`)
- **DP sheets:** a `td.heading[colspan=9]` "First Revised D.P. Scheme", then rows of `h3.download_pdf > a[href="download/dpscheme/<n>.pdf"]` with link text `1` … `35` (**35 sheets**).
- **Full plan and key map:**
  - `<li><strong><a href="download/dpscheme/First Revised DP 2024.pdf"><h2>Final Development Plan-2024(First Revised)</h2></a>`
  - `<a href="download/dpscheme/key map.pdf"><h2>Key Map</h2>`
- **Filter needed:** the same `download/dpscheme/` folder also holds forms (Gujarati file names, "Final list structure expert.pdf"). Take only links whose text is a number, plus the two `h2` items.
- **TP files:** a `td.heading` "T.P.Scheme" with `TPS-1-2` … `TPS-32`, linking to `download/tpscheme/tps-<n>.pdf` (29 links).
- **HEAD:**
  - `dpscheme/1.pdf`: 2,583,765 B, LM 21 Apr 2022, ETag `"095dcd57455d81:0"`.
  - `35.pdf`: 2,499,063 B.
  - `First%20Revised%20DP%202024.pdf`: 20,254,053 B.
  - `key%20map.pdf`: 7,320,494 B (LM 26 Apr 2022).

**Bonus TP source (outside this task, noted for later):** `https://guda.gujarat.gov.in/tpscheme.htm` (fixture `guda/tp_scheme.html`)
- One table with columns `Sr.No.` | `Name of the T.P.Scheme` | `Area in (Hac.)` | `Draft … U/S 48(2)` | `Preliminary … U/S 65` | `Final … U/S 65` | `Remarks`.
- Full-width section rows split it: "Final Town Planning Scheme Sanctioned by Govt.", "Preliminary …", "Draft … and T.P.O. Appointed".
- **The date cells are links** to the stage PDF: `download/dpscheme/draft/19.pdf`, `…/preliminary/19.pdf`, `…/final/19.pdf`, `download/tpscheme/TPS-17.pdf`.
- Name formats: `T.P.S No.19 (Raisan- Randesan- koba)`, `T.P.S. No-11 (Adalaj) PART-A`. Remarks often say "Now In GMC". About 32 schemes.
- HEAD `download/dpscheme/final/13.pdf`: 1,129,625 B, ETag + LM.

### 10.6 Surat — SMC DP (re-checked)

`/Departments/TownPlanningDevelopmentPlans`: re-fetched today. The ZIP links are identical to fixture `smc/dp_sheets.html`, and the footer still says "October 08, 2019".

- **Rows:** `Sheet No.` (`A`…`Z`) | `Name`. The Name cell is a comma-separated **village list** (e.g. A = "Ariyana, Ambheta, Kunkni, Sarol"; B = "Segvachhama, Malgama"), linked to `/Images/Departments/TownPlanning/<L>-<villages>.zip`.
- The lists include villages outside SMC limits (Chalthan, Kadodra, Kamrej-taluka villages). **The page does not state the plan year.**
- **ZIP-only**, so the app can't show these.
- No newer SMC DP page and no LAP page were found. The Town Planning menu has Home, TP Details, Development Plans, Achievements, Future Plan, Building Statistics, … "Future Plan" has no files.
- SMC's area is covered by SUDA's DP-2035 (the variation notifications mark SMC villages with "(SMC)").

### 10.7 Vadodara — VMC, Rajkot — RMC, Ahmedabad — AMC

- **VMC:** `https://vmc.gov.in/TDO.aspx` ("Town Development (B.P.)", fixture `vmc/tdo_bp.html`). One `div.pricing-feature2 ul li a` card has 3 files, none with an ETag:

  | Link text | File | Size / LM |
  |---|---|---|
  | Town Planning Maps | `Zip/Town Planning Maps.zip` (`application/x-zip-compressed`) | 83,635,299 B, 24 Jun 2014 |
  | TP Map - Vadodara (2015) | `pdf/VADODARA  2015 AUGUST.pdf` (two spaces) | 48,947,008 B, 3 Aug 2015 |
  | VUDA Map | `pdf/STRU.pdf` | 4,465,815 B, 16 Jan 2015 |

  These are city-wide composite maps, not a DP. VMC has no DP or LAP page.
- **RMC:** on `https://www.rmc.gov.in/`, the only planning link is "T.P.Map" → `egov.rmc.gov.in/TPMAP` (already covered). No DP or LAP pages.
- **AMC:** the "City Planning" menu in fixture `amc/tp_scheme_information.html` has no DP, LAP or village items. Not re-fetched.
  - A Sept 2026 news report (deshgujarat.com, found by web search, **not verified** on the AMC site) says AMC *proposes* a LAP around Kalupur railway station. So nothing is published yet.

### 10.8 Local Area Plans (LAP)

**What was searched:**
- SUDA page and post sitemaps (no LAP pages);
- AUDA menus (`/RDP/`, `/Content/development-46`, `/LC/`);
- SMC Town Planning menu;
- VMC and the VUDA menu;
- RUDA sitemap;
- GUDA home and downloads;
- TPVD notifications (107 rows, **0 LAP titles**);
- web searches.

**No published LAP map or LAP listing page was found at any authority.**

Web results only give background: LAPs are statutory under §76A of the GTPUD Act (added in 2014), and AUDA's DP-2021 proposed the CBD for a LAP. Neither was **verified** as a published document.

Verdict: **no source for scheme_type LAP right now.** Re-check yearly.

### 10.9 Village maps

- **VUDA DP village maps** (10.4): real village-wise DP sheets for 123 villages. The only true "village map" source.
- **SUDA DP-2035 variations** (10.1 b): each notification names its villages (Gujarati), but the maps are per notification, not per village.
- **SMC DP ZIPs** (10.6): village names per sheet, but ZIP-only.
- **Village lists without maps:** SUDA `/village-list/` (text), RUDA `village-list.html` (table + PDF), AUDA "Village" PDF.
- **Revenue village / gamtal maps:** none of these authorities publishes them. They are only on the state land-record portal AnyROR.
  - Landing page `https://anyror.gujarat.gov.in/` verified: 200, title "-: Any RoR @ Anywhere :-".
  - **Link-out only, not scraped** (PLAN rule). iORA and e-Dhara were not visited.

### 10.10 TPVD (state)

**Pages re-checked:**
- `/Developmentplan`: explanatory text only.
- `/ecitizen/Downloads`: 2 PreDCR `.exe` tools.
- `/sitemap`: no DP or LAP list pages.
- The "Mari Yojana" menu link (`mariyojana.gujarat.gov.in`) is a welfare-schemes portal, not planning.

**There is no statewide list of sanctioned DPs with map files.**

The only statewide signal is the notifications table (§9.1). In the 2026-11-08 fixture, 39 of 107 rows are DP items:
- **Title patterns:** "Modification in Final Development Plan of …", "Variation in Final Development Plan of …", "Proposed Modification in Draft Revised Development Plan 2041 of …".
- **Authorities:** SUDA, AUDA, GUDA, BAUDA, Navsari, Junagadh, Bhavnagar, Mehsana, Nadiad, Kadi, Khedbrahma, Barwala, Savarkundla, Surendranagar-Wadhwan and others.

These are useful as `notification` files and change signals, not as maps.

### 10.11 Catalog modelling (proposal, needs a decision)

| Source | Record granularity | scheme_type | scheme_no | name_en | status / status_label | files |
|---|---|---|---|---|---|---|
| SUDA DP-2035 sanctioned | 1 record | DP | `2035` | `SUDA area` | `final` (or `unknown`) / "Sanctioned 08-10-2020, corrigendum 09-11-2020" | index map + base map + 45 sheets (`map`, title = sheet id); sanction PDF (`notification`) |
| SUDA DP-2035 variations | 1 record **per notification group** (11) | DP | `2035-var-<yyyy-mm-dd>` | villages from the મોજે line (or "Sheets 2-22") | `unknown` / "Proposed variation u/s 19, notified dd-mm-yyyy" | gazette + notification (`notification`), maps (`map`) |
| SUDA DP-2004, DP-1986 | 1 record each | DP | `2004`, `1986` | `SUDA area` | `unknown` / "Superseded DP (low-res sheets)" | sheets (`map`) |
| SUDA draft DP-2035 sets | 1 record each, or skip | DP | `2035-draft-2016` / `2035-draft-us16-2017` / `2035-draft-2019` | `SUDA area` | `draft` / page title | sheets (`map`) |
| AUDA | 1 record per plan year | DP | `1987`, `2002`, `2021`, `2022` | `AUDA area` | `unknown` + row title | the map row (`map`); rows 1–3, 7, 9 as `notification` on the 2021 record; GDCR rows as `other` |
| RUDA | 1 record per plan | DP | `1988`, `2004`, `2031`, `existing-2012` | `RUDA area` | `unknown` / "Development Plan 2031" etc. | main PDF (`map`), Land Use PDF (`other`), 29 grid sheets (`map`, title "Grid sheet 01") |
| VUDA village maps | **1 record per village** (123) | VILLAGE | `dp-2012` | village name from the Name cell | `unknown` / "DP village map u/s 17, 2nd Revised DP 18-01-2012" | 1–5 sheet PDFs (`map`, title = link text) |
| GUDA | 1 record | DP | `2024` | `GUDA area` | `unknown` / "Final Development Plan-2024 (First Revised)" | full plan + key map + 35 sheets (`map`) |
| SMC DP | skip, or 1 record with 26 ZIPs | DP | (year unknown) | `SMC sheets` | `unknown` | **ZIP-only**: leave out, or mark as not viewable |
| VMC | skip, or 1 "other" record | – | – | – | – | ZIP + 2 large PDFs |

**Notes**
- The status enum has no clean value for a sanctioned DP. Mapping "sanctioned final DP" to `final` reads naturally; otherwise use `unknown` + `status_label`.
- **Large files** should be HEAD-only, with the size shown in the app: AUDA 323 MB and 53 MB, RUDA 113 MB, SUDA variation maps up to 69 MB.
- SUDA JPGs send Content-Length only.

### 10.12 New fixtures (all fetched 2026-11-09)

Paths are relative to `pipeline/fixtures/`.

| Fixture | Source URL |
|---|---|
| `suda/dp_index.html` | https://www.sudaonline.org/development-plans/ |
| `suda/dp2035_variations.html` | https://www.sudaonline.org/development-plans/sanction-dp-2035-proposed-variation/ |
| `suda/dp2004_sheets.html` | https://www.sudaonline.org/development-plans/development-plan-2004/ |
| `suda/dp1986_sheets.html` | https://www.sudaonline.org/development-plans/development-plan-1986/ |
| `suda/dp2035_page.html` | https://www.sudaonline.org/development-plans/development-plan-2035/ |
| `suda/dp2035_proposed_us16_sheets.html` | https://www.sudaonline.org/development-plans/proposed-land-use-plan-submitted-us-16/ |
| `suda/dp2035_proposed_2016_sheets.html` | https://www.sudaonline.org/development-plans/proposed-land-use-plans/ |
| `suda/dp2035_online_data_sheets.html` | https://www.sudaonline.org/online-data-dp-sheet-2035/ |
| `suda/authority_map.html` | https://www.sudaonline.org/suda-authority-map/ |
| `suda/village_list.html` | https://www.sudaonline.org/village-list/ |
| `ruda/development_plans.html` | https://rajkotuda.com/development-plans.html |
| `ruda/dp2031_grid_sheets.html` | https://rajkotuda.com/devlopment-plan-2031.html |
| `ruda/existing_dp2012_grid_sheets.html` | https://rajkotuda.com/grid-wise-existing-devlopment-plan.html |
| `ruda/existing_lu2012_grid_sheets.html` | https://rajkotuda.com/grid-wise-existing-land-use-plan.html |
| `ruda/village_list.html` | https://rajkotuda.com/village-list.html |
| `vuda/dp_village_maps.html` | https://www.vuda.co.in/dpvillagemaps.htm |
| `vuda/dp_maps.html` | https://www.vuda.co.in/dpmaps.htm |
| `vuda/development.html` | https://www.vuda.co.in/development.htm |
| `guda/downloads.html` | https://guda.gujarat.gov.in/resources.htm |
| `guda/tp_scheme.html` | https://guda.gujarat.gov.in/tpscheme.htm |
| `guda/home.html` | https://guda.gujarat.gov.in/ |
| `vmc/tdo_bp.html` | https://vmc.gov.in/TDO.aspx |

These existing fixtures were re-checked today and are unchanged (links identical): `suda/dp2035_sheets.html`, `auda/rdp.html`, `smc/dp_sheets.html`, `ruda/development_plans_download.html`.

### 10.13 Not verified

- What the RUDA grid sets actually contain (their labels and folder names contradict each other).
- What the SUDA 2016 and 2019 sheet sets are.
- What VUDA's `V<n>` sheet labels mean.
- Contents of the AUDA "Village" PDF and of the RUDA `images/village-list.jpg`.
- Whether SUDA JPGs ever send ETag/Last-Modified (HEAD today: no).
- The LAP news items (AMC's Kalupur LAP proposal; "19 LAPs returned to AUDA"), which come from web search only.
