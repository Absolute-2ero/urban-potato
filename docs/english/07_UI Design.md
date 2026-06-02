# UI Design Document

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## 1. Design Principles

| Principle | Description |
|-----------|-------------|
| **Healthy yet appetizing** | Green as the primary tone conveys health; warm amber accents stimulate appetite. Avoid clinical cold blue-white palettes. |
| **Visualize information confidence** | Diet labels must distinguish between "confirmed" and "inferred." Allergen warnings must be visually distinct from general information. |
| **Search-first** | The search bar must be visible above the fold on every page. The Facet panel must always be reachable and must not be pushed out of the viewport by content. |
| **Progressive disclosure** | Relevance explanations and nutrition details are collapsed by default; users expand them on demand so default browsing is uncluttered. |
| **Accessibility first** | Allergen warnings must not rely on color alone (for color-blind users). Use triple encoding: icon + text + color. |

---

## 2. Color System

### 2.1 Brand Colors

| Role | Hex | RGB | Usage |
|------|-----|-----|-------|
| Primary Green | `#2D9B5A` | rgb(45, 155, 90) | Primary action buttons, links, active states |
| Primary Green Light | `#4DB87A` | rgb(77, 184, 122) | Hover state, progress bars |
| Primary Green Dark | `#1E7A42` | rgb(30, 122, 66) | Pressed state |
| Secondary Amber | `#F5A623` | rgb(245, 166, 35) | Secondary highlights, rating stars, over-calorie progress |
| Soft Teal | `#3BBFBF` | rgb(59, 191, 191) | Diet profile page background gradient, empty-state illustrations |

### 2.2 Semantic Colors

| Role | Hex | Usage |
|------|-----|-------|
| Allergen Warning | `#E85454` | Allergen warning badges, danger alerts (triple encoding: color + ⚠️ icon + text) |
| Success | `#52C41A` | Action success feedback, goal achieved |
| Warning | `#FAAD14` | Approaching goal limit (calorie ≥ 90%) |
| Info | `#1677FF` | Informational text links, tooltips |

### 2.3 Neutral Colors

| Role | Hex | Usage |
|------|-----|-------|
| Page Background | `#F7F3EE` | Global background (warm sand-white; avoids the coldness of pure white) |
| Card Background | `#FFFFFF` | Search result cards, dialogs |
| Border / Divider | `#E8E0D5` | Card borders, dividers |
| Body Text | `#1E2A2A` | Dark charcoal; primary content |
| Secondary Text | `#6B7A7A` | Supporting descriptions, labels |
| Placeholder Text | `#AAB4B4` | Input placeholder |

### 2.4 Diet Label Color Codes

Consistent color coding is applied to diet types across the entire project:

| Type | Background | Text Color | Notes |
|------|------------|------------|-------|
| vegan | `#E8F5E9` | `#2D9B5A` | Fully plant-based, green palette |
| vegetarian | `#F1F8E9` | `#558B2F` | Vegetarian, light green |
| halal | `#E3F2FD` | `#1565C0` | Halal, blue palette |
| kosher | `#EDE7F6` | `#4527A0` | Kosher, purple |
| gluten-free | `#FFF8E1` | `#F57F17` | Gluten-free, golden yellow |
| dairy-free | `#E0F7FA` | `#00838F` | Dairy-free, teal |
| keto | `#F3E5F5` | `#6A1B9A` | Ketogenic, deep purple |
| high-protein | `#FFEBEE` | `#B71C1C` | High-protein, deep red |
| low-carb | `#FFF3E0` | `#E65100` | Low-carb, orange |
| organic | `#E8F5E9` | `#1B5E20` | Organic, dark green |

---

## 3. Typography System

### 3.1 Font Stack

- **Primary font:** `"PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif`
- **Numbers / code:** `"SF Mono", "Fira Code", monospace` (used for nutrition data display)

### 3.2 Type Scale

| Context | Size | Weight | Line Height | Usage |
|---------|------|--------|-------------|-------|
| Hero title | 36px | 700 | 1.3 | Homepage main tagline |
| Page heading | 24px | 700 | 1.4 | Page H1 |
| Card title | 18px | 600 | 1.4 | Restaurant name |
| Body text | 14px | 400 | 1.6 | Descriptions, supporting copy |
| Small label | 12px | 400 | 1.5 | Diet label badge text |
| Micro annotation | 11px | 400 | 1.4 | Data source attribution |
| Nutrition number | 16px | 600 | 1.2 | Calorie / protein values (monospace) |

---

## 4. Spacing & Layout

- **Base unit:** 8px
- **Spacing scale:** xs=4px / sm=8px / md=16px / lg=24px / xl=32px / xxl=48px
- **Max page width:** 1200px (centered)
- **Content horizontal padding:** 24px (desktop) / 16px (tablet)

### Page Layout Template

```
┌─────────────────────────────────────────────────────┐
│  Header (search bar + user menu)        height: 64px │
├─────────────────────────────────────────────────────┤
│  Facet Panel (240px)   │  Search Results (fluid)     │
│                        │                             │
│  Diet Type  □ vegan    │  [Result Card] [Result Card]│
│             □ halal    │  [Result Card] [Result Card]│
│  Cuisine    □ Chinese  │                             │
│             □ Japanese │  [Pagination]               │
│  Price      ○ $  ○ $$ │                             │
└────────────────────────┴─────────────────────────────┘
```

---

## 5. Component Specifications

### 5.1 Search Bar

- Height: 48px (homepage Hero area) / 40px (embedded in Header)
- Border radius: 24px (pill shape)
- Border: `1px solid #E8E0D5`; on focus: `2px solid #2D9B5A`
- Inline search icon (left side, 16px, `#AAB4B4`)
- Autocomplete dropdown: `border-radius: 12px`, `box-shadow: 0 8px 24px rgba(30,42,42,0.12)`

### 5.2 Diet Label Badge

```
┌──────────────────┐
│  🌿 Vegan        │   Background: #E8F5E9, Text: #2D9B5A
└──────────────────┘
Border radius: 999px (pill)
Padding: 4px 10px
Font size: 12px
Icon: 16px SVG
```

"Inferred" labels (confidence=inferred) get a dashed border:
```
border: 1px dashed #2D9B5A;  /* dashed = not confirmed */
```

### 5.3 Allergen Warning Badge

```
┌──────────────────────────────────┐
│  ⚠️  Contains Peanuts — Allergy Alert  │
└──────────────────────────────────┘
Background: #FFF0F0
Border: 1px solid #E85454
Text color: #E85454
Font weight: 600
Border radius: 6px
aria-role: "alert"
```

### 5.4 Primary Action Button

```
Primary Button:
  background: #2D9B5A
  hover: #4DB87A
  active: #1E7A42
  color: #FFFFFF
  height: 40px
  border-radius: 8px
  font-size: 14px
  font-weight: 600
  padding: 0 20px
```

### 5.5 Search Result Card

```
┌─────────────────────────────────────────────────────┐
│  Restaurant Name                ★ 4.6   ¥¥   820m  │
│  Chinese · Vegetarian                                │
│                                                      │
│  [🌿 Vegan] [🚫 Gluten-Free]  ⚠️ Contains Peanuts  │
│                                                      │
│  "Offers fully <em>vegan</em> set meals, all        │
│   ingredients organically certified..."              │
│                                                      │
│  [Diet Match: ████████░░ 80%]      [View Details →] │
└─────────────────────────────────────────────────────┘
Border radius: 12px
Shadow: 0 2px 8px rgba(30,42,42,0.08)
Hover: deeper box-shadow + translateY(-2px)
Border: 1px solid #E8E0D5
```

### 5.6 Nutrition Progress Bar

```
Calories:  1450 / 2000 kcal  ████████████░░░░░░░  72%
Protein:   78g  / 120g       ████████████░░░░░░░  65%
Fat:       52g  / 65g        █████████████████░░  80%
Carbs:     165g / 250g       █████████████░░░░░░  66%
```

- Progress < 80%: `#2D9B5A` (green)
- Progress 80–99%: `#FAAD14` (yellow)
- Progress ≥ 100%: `#E85454` (red)
- Bar height: 8px, border radius: 4px

---

## 6. Icon System

- **Style:** Outline (line-art) primary, 24px base size
- **Primary icon library:** Ant Design Icons (included in Ant Design 5.x)
- **Diet type icons:** Custom SVG, following this document's color guidelines
- **Stroke:** 2px, `stroke-linecap: round`, `stroke-linejoin: round`

---

## 7. Empty State Design

| Scenario | Illustration | Copy |
|----------|-------------|------|
| No search results | Magnifying glass + falling veggie leaves | "No restaurants matched your filters — try removing some?" |
| No saved restaurants | Empty bookmark + dashed circle | "Nothing saved yet — search and save restaurants you love" |
| No diet log today | Empty bowl + chopsticks | "Nothing logged today — tap '+' to start tracking" |
| Diet profile not set up | Person silhouette + question mark | "Set up your diet profile for more accurate search results" |

Empty-state illustrations use the `empty-state` size preset (320×240), with muted brand colors on a `#F7F3EE` background.

---

## 8. Responsive Breakpoints

| Breakpoint | Width | Layout Change |
|------------|-------|--------------|
| desktop (xl) | ≥ 1200px | Facet panel fixed 240px left column + fluid results area |
| laptop (lg) | 992–1199px | Facet panel collapses into a top filter bar |
| tablet (md) | 768–991px | Single-column layout, filters collapsed |
| mobile (sm) | < 768px | v1.0 not optimized for mobile; horizontal scroll allowed |

---

## 9. Accessibility Standards

- Minimum tap target size for all interactive elements: 44×44px
- Color contrast: body text `#1E2A2A` on `#F7F3EE` = 10.2:1 (AAA)
- Allergen warnings: color + ⚠️ icon + `aria-role="alert"` triple encoding; legible for color-blind users
- Search result cards: `<article>` semantic tag with `aria-label="[Restaurant Name]"`
- Diet labels: `title` attribute provides a full description (e.g. `title="Fully vegan — contains no animal products"`)