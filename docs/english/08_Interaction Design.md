# Interaction Design

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## 1. Site Map

```
/                           Home (search entry + feature intro + About MacroBite)
├── /search                 Search Results page (with filter tags + Facet panel)
│   └── /restaurant/:id     Restaurant Detail page
├── /diet                   Diet Tracking tab
│   ├── /diet/log           Today's Diet Log
│   └── /diet/profile       Diet Profile Settings
├── /saved                  Saved / Favourite Restaurants
├── /profile                User Profile (favourites, preferences)
├── /settings               Settings (preferences, language, account)
└── /auth
    ├── /auth/login         Login page
    └── /auth/register      Register page (includes preference onboarding step)
```

---

## 2. App Shell & Navigation

### 2.1 Bottom Tab Bar

The app uses a two-tab bottom navigation bar present on all main screens:

```
┌─────────────────────────────────────────┐
│                                         │
│          [ Page Content ]               │
│                                         │
├─────────────────────────────────────────┤
│   🔍 Discover        🥗 Diet Tracking   │
└─────────────────────────────────────────┘
```

| Tab | Icon | Route | Description |
|-----|------|-------|-------------|
| Discover | 🔍 | `/` → `/search` | Restaurant search, results, and detail pages |
| Diet Tracking | 🥗 | `/diet/log` | Daily food logging and nutrition goals |

The tab bar is hidden on full-screen sub-pages (e.g. `/restaurant/:id`) but a back button is shown instead.

### 2.2 Header

The header is present on all pages and contains:
- **Left:** MacroBite logo (links to `/`)
- **Right (logged out):** Login / Register buttons
- **Right (logged in):** Profile avatar → dropdown (Profile, Settings, Logout)
- **Far right (always):** EN / 中文 language toggle button

---

## 3. Language Toggle (EN / 中文)

- A toggle button in the header is visible on every page: **`EN | 中文`**
- Clicking switches the entire UI between English and Chinese
- The selected language is persisted in `localStorage` and applied on every page load
- All static UI text, labels, placeholders, toasts, and error messages switch language
- Restaurant names and descriptions served by the API are displayed as-is (the API returns both `name_zh` and `name_en`; the correct field is chosen based on current language)
- Default language: detected from the browser's `navigator.language`; falls back to English

---

## 4. Core Interaction Flows

### 4.1 Discover Tab — Home State (Pre-Search)

When the user lands on the Discover tab with no active search, the page shows a clean, Google-style layout:

```
┌─────────────────────────────────────────────────────┐
│  Header (logo + lang toggle + user menu)             │
├─────────────────────────────────────────────────────┤
│                                                      │
│            🌿  MacroBite                             │
│         Find food that fits you                      │
│                                                      │
│      ┌──────────────────────────────────┐            │
│      │ 🔍  Search restaurants...        │            │
│      └──────────────────────────────────┘            │
│                                                      │
│   Quick filters:                                     │
│   [🌿 Vegan] [🥗 Vegetarian] [🌾 Gluten-Free]        │
│   [🕌 Halal] [✡️ Kosher] [🥩 High-Protein]           │
│                                                      │
│   ── Recommended for you ─────────────────────────  │
│   [Restaurant Card]  [Restaurant Card]  [Card]       │
│                                                      │
│   ── About MacroBite ──────────────────────────────  │
│   (see Section 9)                                    │
└─────────────────────────────────────────────────────┘
```

- The search bar auto-focuses 300ms after page load
- If the user is logged in and has a diet profile, the "Recommended for you" section is populated using their default filter preferences
- If logged out, recommendations show popular/highly rated restaurants
- Quick filter tags below the search bar: clicking one fills the search bar and executes a search immediately
- Users without a profile see a soft prompt banner: "Set up your diet profile for personalised results →" (dismissible)

### 4.2 Main Search Flow

```
User types in the search bar
    │
    ├─ ≥ 2 characters typed → Autocomplete dropdown (debounced 200ms)
    │   ├─ User clicks a suggestion → fills search bar, executes search
    │   └─ User keeps typing → dropdown refreshes in real time
    │
    └─ User presses Enter or clicks the search button
        → Navigate to /search?q=...
        → Results page loads (Skeleton placeholders → real content ≤500ms)
        │
        ├─ Filter tags (below search bar, pill-shaped):
        │   ├─ Active filters shown as removable chips: [🌿 Vegan ×] [Gluten-Free ×]
        │   ├─ "+ Add filter" button opens a filter selector dropdown or sheet
        │   └─ Removing a chip → URL params update, results reload
        │
        ├─ Left Facet panel (desktop) / Top filter bar (tablet):
        │   ├─ Checking / unchecking a facet → URL params update, results reload
        │   └─ Selected facets are mirrored as chips below the search bar
        │
        ├─ Top sort toggle: Relevance / Diet Match / Rating / Distance
        │   → Switching sort mode → results re-ranked (client-side re-sort, no refetch)
        │
        └─ Clicking a result card → navigate to /restaurant/:id
```

If the user is logged in, their saved diet profile preferences are **pre-applied as default filters** when they first arrive at the search page. These can be removed individually for a single session without changing their saved profile.

### 4.3 Food Search & Diet Log Entry Flow

```
User opens /diet/log
    → Taps "+ Add Food"
    → Search input appears (Modal or bottom Drawer)
        │
        User types food name
        │
        ├─ Database hit → shows food list (with calorie / protein preview)
        │   └─ User selects a food → goes to portion input step
        │
        └─ No database match
            → Shows "This food isn't in our database. Add it manually?"
            → User taps "Add Manually" → manual entry form appears
                Fields: name, calories (kcal/100g), protein, fat, carbs,
                        diet labels (multi-select), optional: sodium, fibre
            → User fills in fields → taps "Save & Use"
                → POST /api/food/manual → saved to personal library → portion input step
            → Or taps "Cancel" → returns to search input

Portion input step:
    → Shows food name + grams input + meal type selector (Breakfast / Lunch / Dinner / Snack)
    → Real-time calorie preview: "This serving = approx. XXX kcal"
    → User taps "Add" → POST /api/diet/log → log list refreshes
```

### 4.4 Registration & Preference Onboarding Flow

```
User clicks "Register"
    → /auth/register: enter username, email, password
    → On success → redirect to onboarding step (not home)

Onboarding Step — "Set your food preferences" (skippable):
    → Multi-select diet labels:
        □ Vegan  □ Vegetarian  □ Halal  □ Gluten-Free  □ Keto  □ High-Protein ...
    → Multi-select allergens:
        □ Peanuts  □ Tree Nuts  □ Shellfish  □ Soy  □ Gluten  [+ Add other]
    → Optional calorie / macro goals
    → "Save & Start" → PUT /api/diet/profile → redirect to Home

    OR "Skip for now" → redirect to Home (profile remains empty; soft prompt shown on Discover tab)
```

These preferences become the user's **default filters** — they are automatically applied whenever the user runs a search, and can be updated anytime in Settings.

### 4.5 Diet Profile Settings Flow

```
User opens /diet/profile (or Settings → Diet Preferences)
    → Shows current profile (empty profile shows onboarding prompt)
    │
    Diet type section (multi-select checkbox group):
        □ Vegan         □ Vegetarian
        □ Halal         □ Gluten-Free
        ... (15 types, expandable to show all)
    │
    Allergens section (multi-select, common allergens + custom input):
        □ Peanuts  □ Tree Nuts  □ Shellfish  □ Soy  □ Gluten
        [+ Add other allergen]
    │
    Daily goals section (number inputs, all optional):
        Calorie goal: [____] kcal
        Protein: [____] g    Fat: [____] g    Carbs: [____] g
    │
    "Save Profile" → PUT /api/diet/profile
        → Success toast: "Profile updated — your searches will now reflect your dietary needs"
```

---

## 5. Page Interaction Specifications

### 5.1 Home / Discover Tab ( / )

**Core elements:**
- Hero area: tagline + subtitle + centered search bar
- Quick-select diet type tags below the search bar (click to search immediately)
- "Recommended for you" card row (personalised if logged in, popular if not)
- About MacroBite section (see Section 9)
- Header shows Login / Register if logged out

**Interaction details:**
- Search bar auto-focuses after 300ms
- Quick filter tags: hover → color deepens + slight lift (`translateY(-2px)`)
- First visit (no session): no forced login; anonymous users can search freely

### 5.2 Search Results Page ( /search )

**State management:**
- URL params are the single source of truth: `?q=vegan&diet_labels=vegan&sort=default&page=1`
- Browser back / forward works correctly (URL-driven)

**Loading states:**
- Initial load: results area shows Skeleton (3 card skeletons)
- Facet / filter change: semi-transparent overlay + spinner over existing results (results not cleared)
- Autocomplete: debounced 200ms, max 8 suggestions

**Empty results state:**
- Shows empty-state illustration
- Suggestions area:
  - "Try removing the [diet_labels filter]" (one-click remove)
  - "Similar restaurants in nearby areas" (fallback, if data available)

**Relevance explanation (expandable):**
- Each result card has a collapsed section: "Why is this recommended?"
- Expanded view shows:
  - BM25 keyword hits: `"vegan" matched dish names × 3, description × 1`
  - Diet label match: `✅ vegan (restaurant-level confirmed)`
  - Conflicts: `⚠️ Contains your allergen: Peanuts`

### 5.3 Restaurant Detail Page ( /restaurant/:id )

**Layout:**
- Left column (60%): restaurant info + menu items
- Right column (40%): map (iframe embed) + opening hours + Save button

**Menu list interaction:**
- Default sort: diet label match score (items matching user's profile appear first)
- Each item shows: name + price + diet labels + calories (if available)
- Tap item to expand nutrition details (protein / fat / carbs)

**Save / Favourite button:**
- Logged out: tap → toast "Log in to save restaurants"
- Logged in, not saved: hollow bookmark icon → tap → fills solid + "Saved!" animation
- Logged in, already saved: solid icon → tap → confirm unsave dialog

**Relevance feedback:**
- Bottom card: "Was this result helpful?"
- [👍 Yes]  [👎 No]
- On tap: button moves to selected state, POST /api/feedback, toast "Thanks for your feedback"

### 5.4 Diet Log Page ( /diet/log )

**Date navigation:**
- Top date bar: ← [Today 2026-05-22] → (tap arrows to change day)
- Tap the date text → calendar picker appears (DatePicker)

**Meal group layout:**
```
Breakfast ───────────────────────────── Total: 350 kcal
  Oatmeal 200g              136 kcal    [✏️] [×]
  Blueberries 100g           57 kcal    [✏️] [×]

Lunch ───────────────────────────────── Total: 720 kcal
  Red-braised Pork 100g     395 kcal    [✏️] [×]
  ...

[+ Add Food]
```

**Sticky daily summary (bottom):**
- Fixed at the bottom of the page
- Shows: calorie progress bar + macronutrient progress bars
- Tap summary area → expands full nutrition breakdown table

### 5.5 Profile Page ( /profile )

**Sections:**
- User info: avatar, username, member since date
- Saved restaurants: grid of favourite restaurant cards (links to `/restaurant/:id`)
  - Empty state: "No saved restaurants yet — heart ones you love while browsing"
- Quick link to Settings

### 5.6 Settings Page ( /settings )

**Sections:**

| Section | Contents |
|---------|----------|
| Diet Preferences | Same form as `/diet/profile` — edit default filter tags, allergens, and macro goals |
| Language | EN / 中文 toggle (mirrors the header toggle) |
| Account | Change password, change email |
| About MacroBite | Short description + link to the About section |

Changes save immediately (auto-save on change) or via explicit "Save" button per section.

---

## 6. General Interaction Standards

**Toast notifications:**
- Success: green, auto-dismisses after 3s
- Error: red, requires manual dismiss
- Position: top-center of the page

**Modals:**
- Max width: 560px
- Background overlay: `rgba(0,0,0,0.45)`
- Clicking overlay closes (non-destructive actions only)
- Destructive actions (e.g. delete log entry): use a confirmation dialog with explicit "Delete" button

**Form validation:**
- Real-time validation (onChange, not onSubmit)
- Error messages displayed below the field, red, 12px

**Loading feedback:**
- Button actions: button shows `loading` state (prevents double submission)
- Page loads: Skeleton component placeholders
- Load more: Spin at the bottom of lists

---

## 7. Keyboard Interactions

| Shortcut | Context | Action |
|----------|---------|--------|
| `/` | Global | Focus the search bar |
| `Esc` | Search bar focused | Clear search bar / close Autocomplete |
| `↑ ↓` | Autocomplete open | Navigate suggestions |
| `Enter` | Autocomplete open | Select highlighted suggestion |
| `Tab` | Forms | Move focus to next input |

---

## 8. Responsive Breakpoints

| Breakpoint | Width | Layout Change |
|------------|-------|--------------|
| desktop (xl) | ≥ 1200px | Facet panel as fixed 240px left column |
| laptop (lg) | 992–1199px | Facet panel collapses into top filter bar |
| tablet (md) | 768–991px | Single-column layout, filters collapsed |
| mobile (sm) | < 768px | v1.0: not mobile-optimised; horizontal scroll permitted |

---

## 9. About MacroBite Section

The About section is embedded at the bottom of the Discover / Home page and also linked from the Settings page. It is always accessible without login.

**Content:**

> **About MacroBite**
>
> MacroBite helps you find restaurants that actually fit your diet — whether you're vegan, avoiding allergens, hitting a protein goal, or just curious about what you're eating.
>
> Search any restaurant or cuisine, filter by your dietary needs, and track your daily nutrition all in one place. Your preferences travel with you: set them once, and every search is personalised to you.
>
> MacroBite is built for people who care about what they eat, without making it complicated.

**Layout:** Full-width section with a soft teal background (`#3BBFBF` at 10% opacity), the MacroBite logo, the copy above, and a "Get started — it's free" CTA button (visible only when logged out).