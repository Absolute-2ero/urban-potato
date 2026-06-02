# Frontend Implementation

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## 1. Directory Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── main.tsx                     # Entry point: ReactDOM.createRoot + Router
│   ├── App.tsx                      # Route configuration (React Router v6)
│   │
│   ├── pages/                       # Page-level components (one per route)
│   │   ├── HomePage.tsx             # /
│   │   ├── SearchPage.tsx           # /search
│   │   ├── RestaurantDetailPage.tsx # /restaurant/:id
│   │   ├── DietLogPage.tsx          # /diet/log
│   │   ├── DietProfilePage.tsx      # /diet/profile
│   │   ├── SavedPage.tsx            # /saved
│   │   ├── ProfilePage.tsx          # /profile
│   │   ├── SettingsPage.tsx         # /settings
│   │   ├── OnboardingPage.tsx       # /onboarding (post-registration preference setup)
│   │   ├── LoginPage.tsx            # /auth/login
│   │   └── RegisterPage.tsx         # /auth/register
│   │
│   ├── components/                  # Reusable components
│   │   ├── layout/
│   │   │   ├── AppHeader.tsx        # Top nav (logo + lang toggle + user menu)
│   │   │   ├── BottomTabBar.tsx     # Bottom tab navigation (Discover / Diet Tracking)
│   │   │   └── AppLayout.tsx        # Overall layout wrapper
│   │   ├── search/
│   │   │   ├── SearchBar.tsx        # Search input + Autocomplete
│   │   │   ├── FilterChips.tsx      # Active filter chips below the search bar
│   │   │   ├── FacetPanel.tsx       # Left-side facet filter panel
│   │   │   ├── ResultCard.tsx       # Single search result card
│   │   │   ├── ResultList.tsx       # Result list + pagination
│   │   │   ├── SortSelector.tsx     # Sort mode toggle
│   │   │   └── RelevanceExplainer.tsx  # "Why is this recommended?" expandable panel
│   │   ├── diet/
│   │   │   ├── FoodSearchModal.tsx  # Food search modal (search DB + manual entry fallback)
│   │   │   ├── ManualFoodForm.tsx   # Manual food entry form (shown when no DB match)
│   │   │   ├── LogEntry.tsx         # Single diet log entry row
│   │   │   ├── NutritionBar.tsx     # Nutrition progress bar (calories/protein/fat/carbs)
│   │   │   └── MealGroup.tsx        # Entries grouped by meal type
│   │   ├── restaurant/
│   │   │   ├── DietBadge.tsx        # Diet label badge (with color mapping)
│   │   │   ├── AllergenWarning.tsx  # Allergen warning badge
│   │   │   └── MenuItemCard.tsx     # Menu item card
│   │   └── common/
│   │       ├── EmptyState.tsx       # Empty state component (with illustration)
│   │       ├── PageSkeleton.tsx     # Page skeleton loader
│   │       └── LanguageToggle.tsx   # EN / 中文 toggle button
│   │
│   ├── illustrations/               # Frontend illustrations (SVG components)
│   │   ├── HeroIllustration.tsx
│   │   ├── EmptySearchState.tsx
│   │   ├── EmptyLogState.tsx
│   │   └── icons/
│   │       ├── VeganIcon.tsx
│   │       ├── HalalIcon.tsx
│   │       ├── GlutenFreeIcon.tsx
│   │       └── ...                  # Remaining diet type icons
│   │
│   ├── store/                       # Zustand global state
│   │   ├── useAuthStore.ts          # User authentication state
│   │   ├── useSearchStore.ts        # Search params and results cache
│   │   ├── useDietStore.ts          # Today's diet log and profile
│   │   └── useLanguageStore.ts      # Active language (en / zh)
│   │
│   ├── api/                         # API call functions (Axios wrappers)
│   │   ├── client.ts                # Axios instance (with interceptors)
│   │   ├── auth.ts
│   │   ├── food.ts
│   │   ├── diet.ts
│   │   ├── search.ts
│   │   └── restaurants.ts
│   │
│   ├── hooks/                       # Custom hooks
│   │   ├── useSearch.ts             # Search logic (URL param sync)
│   │   ├── useFoodSearch.ts         # Food search (static DB + personal library; manual entry state)
│   │   ├── useDebounce.ts           # Debounce (used by Autocomplete)
│   │   └── useLanguage.ts           # Language toggle + persistence
│   │
│   ├── i18n/                        # Internationalisation strings
│   │   ├── en.ts                    # English UI strings
│   │   ├── zh.ts                    # Chinese UI strings
│   │   └── index.ts                 # t() helper — returns string for active language
│   │
│   ├── constants/
│   │   ├── dietLabels.ts            # Diet label config (label → color → icon)
│   │   └── routes.ts                # Route path constants
│   │
│   └── types/
│       ├── restaurant.ts            # Restaurant, MenuItem type definitions
│       ├── food.ts                  # FoodItem, UserFoodItem, FoodLogEntry types
│       └── search.ts                # SearchResult, Facet types
│
├── package.json
├── tsconfig.json
└── vite.config.ts                   # Vite build config
```

---

## 2. Route Configuration

```tsx
// App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';

const App: React.FC = () => (
  <BrowserRouter>
    <AppLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/restaurant/:id" element={<RestaurantDetailPage />} />
        <Route path="/diet/log" element={<PrivateRoute><DietLogPage /></PrivateRoute>} />
        <Route path="/diet/profile" element={<PrivateRoute><DietProfilePage /></PrivateRoute>} />
        <Route path="/saved" element={<PrivateRoute><SavedPage /></PrivateRoute>} />
        <Route path="/profile" element={<PrivateRoute><ProfilePage /></PrivateRoute>} />
        <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
        <Route path="/onboarding" element={<PrivateRoute><OnboardingPage /></PrivateRoute>} />
        <Route path="/auth/login" element={<LoginPage />} />
        <Route path="/auth/register" element={<RegisterPage />} />
      </Routes>
    </AppLayout>
  </BrowserRouter>
);
```

`PrivateRoute` component: redirects unauthenticated users to `/auth/login`, preserving the intended destination in a `redirect` URL param.

After successful registration, the user is redirected to `/onboarding` instead of home. The onboarding page handles the preference setup step and then redirects to `/`.

---

## 3. State Management

### 3.1 useAuthStore (Authentication)

```typescript
// store/useAuthStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  user: User | null;
  isLoggedIn: boolean;
  setUser: (user: User | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isLoggedIn: false,
      setUser: (user) => set({ user, isLoggedIn: !!user }),
      logout: () => set({ user: null, isLoggedIn: false }),
    }),
    { name: 'auth-storage' }
  )
);
```

### 3.2 useSearchStore (Search State)

```typescript
// store/useSearchStore.ts
interface SearchState {
  query: string;
  dietLabels: string[];
  priceLevel: number[];
  ratingMin: number | null;
  sortMode: SortMode;
  page: number;
  results: SearchResult | null;
  loading: boolean;
  setParams: (params: Partial<SearchParams>) => void;
  setResults: (results: SearchResult) => void;
}
```

**Key design:** URL params are the single source of truth for search state. The `useSearch` hook watches for URL param changes, syncs them to the store, and triggers the API call.

When a logged-in user first opens the search page with no URL params, their saved diet profile preferences are loaded from `useDietStore` and applied as the initial default filters before the first search fires.

### 3.3 useLanguageStore (Language)

```typescript
// store/useLanguageStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Lang = 'en' | 'zh';

interface LanguageState {
  lang: Lang;
  setLang: (lang: Lang) => void;
}

export const useLanguageStore = create<LanguageState>()(
  persist(
    (set) => ({
      lang: (navigator.language.startsWith('zh') ? 'zh' : 'en') as Lang,
      setLang: (lang) => set({ lang }),
    }),
    { name: 'language-preference' }
  )
);
```

---

## 4. Internationalisation (i18n)

All static UI text is stored in locale files and accessed via a `t()` helper. No third-party i18n library is required for v1.0.

```typescript
// i18n/en.ts
export const en = {
  search: {
    placeholder: 'Search vegan, halal, gluten-free restaurants...',
    noResults: 'No restaurants matched your filters — try removing some?',
    addFilter: '+ Add filter',
    sortRelevance: 'Relevance',
    sortDietMatch: 'Diet Match',
    sortRating: 'Rating',
    sortDistance: 'Distance',
  },
  diet: {
    addFood: '+ Add Food',
    breakfast: 'Breakfast',
    lunch: 'Lunch',
    dinner: 'Dinner',
    snack: 'Snack',
    calorieGoal: 'Calorie Goal',
    foodNotFound: "This food isn't in our database. Add it manually?",
    addManually: 'Add Manually',
    saveAndUse: 'Save & Use',
  },
  auth: {
    login: 'Log In',
    register: 'Sign Up',
    logout: 'Log Out',
  },
  nav: {
    discover: 'Discover',
    dietTracking: 'Diet Tracking',
    profile: 'Profile',
    settings: 'Settings',
    about: 'About MacroBite',
  },
  // ...
};

// i18n/zh.ts
export const zh = {
  search: {
    placeholder: '搜索素食、清真、无麸质餐厅...',
    noResults: '没有找到符合条件的餐厅，试试减少过滤条件？',
    addFilter: '+ 添加筛选',
    // ...
  },
  diet: {
    addFood: '+ 添加食物',
    foodNotFound: '数据库中没有此食物，手动添加？',
    addManually: '手动添加',
    saveAndUse: '保存并使用',
    // ...
  },
  // ...
};

// i18n/index.ts
import { useLanguageStore } from '../store/useLanguageStore';
import { en } from './en';
import { zh } from './zh';

export function t(key: string): string {
  const lang = useLanguageStore.getState().lang;
  const strings = lang === 'zh' ? zh : en;
  return key.split('.').reduce((obj: any, k) => obj?.[k], strings) ?? key;
}
```

Restaurant names and descriptions use `name_en` or `name_zh` from the API response based on the active language:

```typescript
const restaurantName = lang === 'zh' ? restaurant.name_zh : restaurant.name_en;
```

---

## 5. Key Component Implementations

### 5.1 BottomTabBar

```tsx
// components/layout/BottomTabBar.tsx
const TABS = [
  { key: 'discover', label: () => t('nav.discover'), icon: <SearchOutlined />, path: '/' },
  { key: 'diet',     label: () => t('nav.dietTracking'), icon: <MedicineBoxOutlined />, path: '/diet/log' },
];

const BottomTabBar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  // Hide on restaurant detail page (show back button instead)
  const hidden = location.pathname.startsWith('/restaurant/');
  if (hidden) return null;

  const activeKey = location.pathname.startsWith('/diet') ? 'diet' : 'discover';

  return (
    <nav className="bottom-tab-bar">
      {TABS.map(tab => (
        <button
          key={tab.key}
          className={`tab-item ${activeKey === tab.key ? 'active' : ''}`}
          onClick={() => navigate(tab.path)}
        >
          {tab.icon}
          <span>{tab.label()}</span>
        </button>
      ))}
    </nav>
  );
};
```

### 5.2 LanguageToggle

```tsx
// components/common/LanguageToggle.tsx
const LanguageToggle: React.FC = () => {
  const { lang, setLang } = useLanguageStore();

  return (
    <button
      className="lang-toggle"
      onClick={() => setLang(lang === 'en' ? 'zh' : 'en')}
      aria-label="Switch language"
    >
      {lang === 'en' ? '中文' : 'EN'}
    </button>
  );
};
```

Rendered in `AppHeader` on every page, next to the user menu.

### 5.3 SearchBar (Search Input + Autocomplete)

```tsx
// components/search/SearchBar.tsx
const SearchBar: React.FC<SearchBarProps> = ({ onSearch }) => {
  const [inputVal, setInputVal] = useState('');
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const debouncedVal = useDebounce(inputVal, 200);
  const lang = useLanguageStore((s) => s.lang);

  useEffect(() => {
    if (debouncedVal.length < 2) {
      setSuggestions([]);
      return;
    }
    searchApi.getSuggestions(debouncedVal).then(setSuggestions);
  }, [debouncedVal]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') onSearch(inputVal);
    if (e.key === 'Escape') setSuggestions([]);
  };

  return (
    <div className="search-bar-wrapper">
      <AutoComplete
        options={suggestions.map(s => ({ value: s.text, label: s.text }))}
        onSelect={(val) => { setInputVal(val); onSearch(val); }}
      >
        <Input
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onKeyDown={handleKeyDown}
          prefix={<SearchOutlined style={{ color: '#AAB4B4' }} />}
          placeholder={t('search.placeholder')}
          style={{ borderRadius: 24, height: 48 }}
        />
      </AutoComplete>
    </div>
  );
};
```

### 5.4 FilterChips (Active Filter Chips Below Search Bar)

```tsx
// components/search/FilterChips.tsx
const FilterChips: React.FC<{ params: SearchParams; onRemove: (key: string, val: string) => void }> = ({
  params,
  onRemove,
}) => {
  const chips = [
    ...params.dietLabels.map(l => ({ key: 'dietLabels', val: l, label: l })),
    ...params.priceLevel.map(p => ({ key: 'priceLevel', val: String(p), label: '¥'.repeat(p) })),
  ];

  if (chips.length === 0) return null;

  return (
    <div className="filter-chips">
      {chips.map(chip => (
        <Tag
          key={`${chip.key}-${chip.val}`}
          closable
          onClose={() => onRemove(chip.key, chip.val)}
          style={{ borderRadius: 999, padding: '2px 10px' }}
        >
          {chip.label}
        </Tag>
      ))}
    </div>
  );
};
```

### 5.5 DietBadge (Diet Label Badge)

```tsx
// components/restaurant/DietBadge.tsx
const DIET_BADGE_CONFIG: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  vegan:         { bg: '#E8F5E9', text: '#2D9B5A', icon: <VeganIcon width={14} height={14} /> },
  vegetarian:    { bg: '#F1F8E9', text: '#558B2F', icon: <VegetarianIcon width={14} height={14} /> },
  halal:         { bg: '#E3F2FD', text: '#1565C0', icon: <HalalIcon width={14} height={14} /> },
  'gluten-free': { bg: '#FFF8E1', text: '#F57F17', icon: <GlutenFreeIcon width={14} height={14} /> },
  // ...
};

const DietBadge: React.FC<{ label: string; confidence?: 'confirmed' | 'inferred' }> = ({
  label,
  confidence = 'confirmed',
}) => {
  const config = DIET_BADGE_CONFIG[label];
  if (!config) return null;

  return (
    <span
      style={{
        backgroundColor: config.bg,
        color: config.text,
        border: confidence === 'inferred' ? `1px dashed ${config.text}` : 'none',
        borderRadius: 999,
        padding: '2px 10px',
        fontSize: 12,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
      title={
        confidence === 'inferred'
          ? `${label} (${t('badge.inferred')})`
          : label
      }
    >
      {config.icon}
      {label}
    </span>
  );
};
```

### 5.6 FoodSearchModal (with Manual Entry Fallback)

```tsx
// components/diet/FoodSearchModal.tsx
type Step = 'search' | 'manual' | 'portion';

const FoodSearchModal: React.FC<Props> = ({ onAdd, onClose }) => {
  const [step, setStep] = useState<Step>('search');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<FoodItem[]>([]);
  const [selectedFood, setSelectedFood] = useState<FoodItem | null>(null);
  const [quantityG, setQuantityG] = useState<number>(100);
  const [mealType, setMealType] = useState<MealType>('lunch');

  const handleSearch = async (q: string) => {
    setQuery(q);
    const res = await foodApi.search(q);
    setResults(res.items);
    // If no results, stay on search step — the empty state prompts manual entry
  };

  const handleSelectFood = (food: FoodItem) => {
    setSelectedFood(food);
    setStep('portion');
  };

  const handleManualSaved = (food: FoodItem) => {
    // After manual entry is saved to personal library, move straight to portion step
    setSelectedFood(food);
    setStep('portion');
  };

  const handleSubmitLog = async () => {
    if (!selectedFood) return;
    await dietApi.addLog({
      food_source: selectedFood.food_source,
      food_id: selectedFood.food_id,
      quantity_g: quantityG,
      meal_type: mealType,
    });
    onAdd();
    onClose();
  };

  return (
    <Modal open onCancel={onClose} footer={null} title={t('diet.addFood')}>
      {step === 'search' && (
        <>
          <Input.Search
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder={t('diet.searchPlaceholder')}
            autoFocus
          />
          {results.length > 0 ? (
            <List
              dataSource={results}
              renderItem={(food) => (
                <List.Item onClick={() => handleSelectFood(food)} style={{ cursor: 'pointer' }}>
                  <span>{food.name_zh}</span>
                  <span style={{ color: '#888' }}>{food.calories} kcal / 100g</span>
                </List.Item>
              )}
            />
          ) : query.length > 0 ? (
            <EmptyState
              message={t('diet.foodNotFound')}
              action={
                <Button onClick={() => setStep('manual')}>{t('diet.addManually')}</Button>
              }
            />
          ) : null}
        </>
      )}

      {step === 'manual' && (
        <ManualFoodForm onSaved={handleManualSaved} onCancel={() => setStep('search')} />
      )}

      {step === 'portion' && selectedFood && (
        <>
          <p><strong>{selectedFood.name_zh}</strong></p>
          <InputNumber
            value={quantityG}
            onChange={(v) => setQuantityG(v ?? 100)}
            min={1}
            addonAfter="g"
          />
          <p style={{ color: '#888' }}>
            ≈ {((selectedFood.calories * quantityG) / 100).toFixed(0)} kcal
          </p>
          <Select value={mealType} onChange={setMealType} style={{ width: '100%' }}>
            {(['breakfast', 'lunch', 'dinner', 'snack'] as MealType[]).map(m => (
              <Select.Option key={m} value={m}>{t(`diet.${m}`)}</Select.Option>
            ))}
          </Select>
          <Button type="primary" onClick={handleSubmitLog} style={{ marginTop: 16, width: '100%' }}>
            {t('diet.addFood')}
          </Button>
        </>
      )}
    </Modal>
  );
};
```

### 5.7 ManualFoodForm

```tsx
// components/diet/ManualFoodForm.tsx
const ManualFoodForm: React.FC<{
  onSaved: (food: FoodItem) => void;
  onCancel: () => void;
}> = ({ onSaved, onCancel }) => {
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    name_zh: '', name_en: '',
    calories: '', protein_g: '', fat_g: '', carb_g: '',
    diet_labels: [] as string[],
  });

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const saved = await foodApi.addManual(form);
      onSaved(saved);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="manual-food-form">
      <Input
        placeholder={t('diet.foodNameZh')}
        value={form.name_zh}
        onChange={(e) => setForm({ ...form, name_zh: e.target.value })}
      />
      <InputNumber
        placeholder="Calories (kcal / 100g)"
        value={form.calories}
        onChange={(v) => setForm({ ...form, calories: String(v) })}
        min={0}
        style={{ width: '100%' }}
      />
      <InputNumber placeholder="Protein (g)" value={form.protein_g}
        onChange={(v) => setForm({ ...form, protein_g: String(v) })} min={0} style={{ width: '100%' }} />
      <InputNumber placeholder="Fat (g)" value={form.fat_g}
        onChange={(v) => setForm({ ...form, fat_g: String(v) })} min={0} style={{ width: '100%' }} />
      <InputNumber placeholder="Carbs (g)" value={form.carb_g}
        onChange={(v) => setForm({ ...form, carb_g: String(v) })} min={0} style={{ width: '100%' }} />
      <Select
        mode="multiple"
        placeholder={t('diet.dietLabels')}
        value={form.diet_labels}
        onChange={(v) => setForm({ ...form, diet_labels: v })}
        style={{ width: '100%' }}
        options={DIET_LABEL_OPTIONS}
      />
      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <Button onClick={onCancel} style={{ flex: 1 }}>Cancel</Button>
        <Button type="primary" onClick={handleSubmit} loading={loading} style={{ flex: 1 }}>
          {t('diet.saveAndUse')}
        </Button>
      </div>
    </div>
  );
};
```

### 5.8 NutritionBar (Nutrition Progress Bar)

```tsx
// components/diet/NutritionBar.tsx
const NutritionBar: React.FC<{
  label: string;
  current: number;
  goal: number | null;
  unit: string;
}> = ({ label, current, goal, unit }) => {
  const pct = goal ? Math.min((current / goal) * 100, 100) : null;
  const color = pct === null ? '#2D9B5A'
              : pct >= 100  ? '#E85454'
              : pct >= 80   ? '#FAAD14'
              : '#2D9B5A';

  return (
    <div className="nutrition-bar">
      <div className="nutrition-bar-header">
        <span>{label}</span>
        <span>{current.toFixed(1)}{unit}{goal ? ` / ${goal}${unit}` : ''}</span>
      </div>
      {pct !== null && (
        <Progress
          percent={pct}
          showInfo={false}
          strokeColor={color}
          strokeWidth={8}
          style={{ margin: 0 }}
        />
      )}
    </div>
  );
};
```

---

## 6. API Client

```typescript
// api/client.ts
import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  withCredentials: true,   // Must send cookies with every request
  timeout: 15000,
});

// Response interceptor: handle 401 globally
client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/auth/login';
    }
    return Promise.reject(err.response?.data?.error || 'Request failed');
  }
);
```

---

## 7. useSearch Hook (URL Param Sync)

```typescript
// hooks/useSearch.ts
import { useSearchParams } from 'react-router-dom';

export function useSearch() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { setResults, setLoading } = useSearchStore();
  const { profile } = useDietStore();

  const params = useMemo(() => ({
    q: searchParams.get('q') || '',
    dietLabels: searchParams.get('diet_labels')?.split(',').filter(Boolean) || [],
    priceLevel: searchParams.get('price_level')?.split(',').map(Number) || [],
    ratingMin: searchParams.get('rating_min') ? Number(searchParams.get('rating_min')) : null,
    sort: (searchParams.get('sort') || 'default') as SortMode,
    page: Number(searchParams.get('page') || 1),
  }), [searchParams]);

  // On first load with no filters, apply the user's saved profile preferences as defaults
  useEffect(() => {
    const hasExplicitFilters = searchParams.has('diet_labels') || searchParams.has('q');
    if (!hasExplicitFilters && profile?.diet_labels?.length) {
      setSearchParams(buildSearchParams({
        ...params,
        dietLabels: profile.diet_labels,
      }), { replace: true });
    }
  }, []);   // Run once on mount only

  useEffect(() => {
    if (!params.q && params.dietLabels.length === 0) return;
    setLoading(true);
    searchApi.search(params)
      .then(setResults)
      .finally(() => setLoading(false));
  }, [params]);   // Re-runs whenever params change

  const updateParams = (updates: Partial<SearchParams>) => {
    const next = { ...params, ...updates, page: 1 };   // Reset to page 1 on filter change
    setSearchParams(buildSearchParams(next));
  };

  return { params, updateParams };
}
```

---

## 8. Build & Environment Variables

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000

# .env.production
VITE_API_BASE_URL=https://api.macrobite.example.com
```

```bash
# Development
npm run dev

# Production build (output to dist/)
npm run build

# Code checks
npm run lint
npm run type-check
```

**Vite config notes:**
```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',   // Proxy API calls in dev to avoid CORS
    },
  },
  build: {
    chunkSizeWarningLimit: 1000,
  },
});
```