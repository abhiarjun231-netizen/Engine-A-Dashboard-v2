# Parthsarthi Capital — Public Dashboard

Editorial-grade HTML dashboard for the multi-engine investment system.
Mobile-first. Reads live JSON from your existing Engine-A-Dashboard-v2 repo.
Deploys free via GitHub Pages.

---

## Files in this folder

```
docs/
├── index.html       Main page structure
├── styles.css       Design system (navy + cream + saffron palette)
├── app.js           Fetches live data, renders all sections
├── assets/
│   └── logo.svg     Chariot-wheel brand mark
└── README.md        This file
```

---

## Deployment to GitHub Pages (10 minutes, mobile-friendly)

### Step 1: Create `docs/` folder in your repo

1. Open GitHub on phone → repo `Engine-A-Dashboard-v2`
2. Tap **Add file** → **Create new file**
3. In the filename box, type: `docs/README.md`
4. Paste any placeholder content (e.g., "Parthsarthi Capital public dashboard")
5. Tap **Commit changes**

This creates the `docs/` folder.

### Step 2: Upload the 4 dashboard files

For each file:

1. Repo → navigate into `docs/` folder
2. Tap **Add file** → **Upload files**
3. Upload `index.html`, `styles.css`, `app.js`
4. Commit: `Initial Parthsarthi dashboard upload`

Then inside `docs/`:

5. Tap **Add file** → **Create new file**
6. Filename: `assets/logo.svg`
7. Paste contents of `logo.svg` from this folder
8. Commit: `Add brand logo`

### Step 3: Enable GitHub Pages

1. Repo → **Settings**
2. Left sidebar → **Pages**
3. **Source**: select **Deploy from a branch**
4. **Branch**: `main`
5. **Folder**: `/docs`
6. Tap **Save**

Wait ~1 minute. GitHub Pages will deploy. You'll see a banner:
> *Your site is live at https://abhiarjun231-netizen.github.io/Engine-A-Dashboard-v2/*

That's your public dashboard URL. Bookmark it. Share it with friends.

---

## What you'll see

**On first load:**
- Animated score counter (0 → 45)
- Auto-fields ticker scrolling in dark navy band
- Regime badge in green (ACTIVE), saffron (CAUTIOUS), or red (FREEZE)
- 8-axis radar showing component health
- 8 expandable component cards with sub-input drill-down
- Score history line chart with regime band shading

**Demo mode:**
If the JSON fetch fails (network issue, JSON not yet committed, etc.), a saffron banner appears at the top reading "Demo mode · Live data not yet available" and embedded sample data renders. This ensures the dashboard ALWAYS looks polished, even before first deployment.

**Auto-refresh:**
Background refresh every 5 minutes. Doesn't interrupt user (unlike Streamlit's auto-refresh).

---

## URLs in the dashboard

The dashboard fetches data from these public URLs in your repo:

```
https://raw.githubusercontent.com/abhiarjun231-netizen/Engine-A-Dashboard-v2/main/data/core/engine_a_current.json
https://raw.githubusercontent.com/abhiarjun231-netizen/Engine-A-Dashboard-v2/main/data/core/engine_a_history.csv
```

If you ever rename the repo or change the JSON path, update `CONFIG.jsonUrl` and `CONFIG.historyUrl` in `app.js`.

---

## Sharing with friends

Send them the GitHub Pages URL:
> *https://abhiarjun231-netizen.github.io/Engine-A-Dashboard-v2/*

They get the read-only premium dashboard. They cannot see Admin, cannot change values, cannot trigger workflows. Just the elegant front-end.

**Do NOT share the Streamlit URL** (`gqp.streamlit.app`) — that's now your private back-office for data entry.

---

## Editing later

To update copy, colors, or layout:

1. GitHub → `docs/index.html` (or `styles.css` or `app.js`) → ✏️ edit button
2. Make changes
3. Commit
4. GitHub Pages redeploys automatically in ~1 minute

No build step. No npm. No dependencies. Vanilla HTML/CSS/JS — the way the web was meant to work.

---

## Customization knobs (in `app.js` `CONFIG` object)

```js
const CONFIG = {
  jsonUrl: "...",           // Path to engine_a_current.json
  historyUrl: "...",        // Path to engine_a_history.csv
  refreshIntervalMs: 300000 // 5 min auto-refresh
};
```

---

## Design notes (for future you)

- Typography: Fraunces (display serif) + DM Sans (body) + JetBrains Mono (data)
- Palette: midnight navy `#0A1628` · cream `#FDFBF5` · saffron `#D97706`
- All animations respect `prefers-reduced-motion`
- Brand mark = 8-spoke chariot wheel (matches 8 Engine A components)
- Watermark of full chakra in upper-right of page (very subtle)
- Devanagari "पार्थसारथि" under English brand name

---

## Brand info

- **Name**: Parthsarthi Capital
- **Tagline**: *Your charioteer in Indian markets*
- **Devanagari**: पार्थसारथि (Krishna's epithet as Arjuna's charioteer)
- **Symbol**: 8-spoke chariot wheel (Sudarshan inspired)

---

*Educational use only. Not investment advice. Markets carry risk of capital loss.*
