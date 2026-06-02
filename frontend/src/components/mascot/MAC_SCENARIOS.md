# Mac the Mascot — Scenarios & Script

Mac is a cheerful broccoli who lives in the bottom-right corner of MacroBite. He reacts to what the user is doing, celebrates wins, gently nudges habits, and occasionally makes dry food jokes. His tone is warm, playful, and never preachy.

---

## Emotion Reference

| `emotion` | Visual | When to use |
|-----------|--------|-------------|
| `idle`    | Neutral smile, gentle bob | Default / nothing notable happening |
| `happy`   | Squinted eyes, blush, bigger smile | Positive choice made |
| `sweat`   | Wide eyes, sweat drop, downturned mouth | High-cal / oily dish selected |
| `excited` | Huge open mouth, arms up, sparkles | Goal hit / personal best |
| `sleep`   | Closed eyes, floating Z's | User inactive for 3+ min |
| `cool`    | Sunglasses, smirk | User is on a streak or acts cool |
| `thinking`| One squint eye, thought bubble | Browsing / no search yet |
| `cheer`   | Giant grin, arms wide, confetti | Milestone / first log / first save |

---

## 1 · Home Page

### On page load (first visit, no prefs set)
- **emotion:** `thinking`
- **message (rotate randomly):**
  - "Hmm, what are we craving today? 🤔"
  - "I've got opinions on where to eat. Just saying."
  - "Let me know your diet and I'll find you something good!"

### On page load (returning user, prefs set)
- **emotion:** `happy`
- **message:** "Welcome back! Ready to eat well? 🥦"

### After 3 min of idle browsing on home
- **emotion:** `sleep`
- **message:** "Psst… I'm napping over here. Wake me when you're hungry. 😴"

### Suggesting a "quest" (random, shown once per session)
- **emotion:** `cool`
- **messages (pick one):**
  - "Today's quest: pick a restaurant 1 km further than usual and walk there. Couch potato status: revoked. 🚶"
  - "Challenge: eat a meal with at least 30 g of protein today. Your muscles will thank you."
  - "Feeling adventurous? Try a cuisine you've never logged before!"
  - "It's [day of week]. Studies show people skip veggies on [same day]. Don't be a statistic. 🥗"
  - "Why not pick something low-sodium today? Your heart is literally begging you."

---

## 2 · Search Page — Browsing & Filters

### No search yet, filter bar visible
- **emotion:** `thinking`
- **message:** "I think you should eat a salad today. Just a vibe I'm getting."

### User types a search query
- **emotion:** `idle`
- **message:** `null` *(Mac goes quiet while the user is typing)*

### Results load (many results)
- **emotion:** `happy`
- **message (rotate):**
  - "Plenty to choose from! I believe in you. 🥦"
  - "{count} options. That's a lot of good decisions waiting to happen."

### Results load (few results, < 3)
- **emotion:** `thinking`
- **message:** "Only {count} match… you're either very specific or very healthy. Respect."

### Results load (zero results)
- **emotion:** `sweat`
- **message:** "Uh oh, nothing showed up! Try fewer filters — or just move somewhere with better food 😅"

### User opens **Health** filter panel
- **emotion:** `happy`
- **message (rotate):**
  - "Filtering for nutrition? You're literally my favourite person."
  - "Low-fat, low-sodium… you're basically a doctor."

### User selects **low-fat** filter
- **emotion:** `happy`
- **message:** "Smart pick. Your arteries are applauding right now. 👏"

### User selects **low-sugar** filter
- **emotion:** `happy`
- **message:** "No sugar rush, no crash. Smooth brain energy all day. 🧠"

### User selects **high-protein** filter
- **emotion:** `excited`
- **message:** "GAINS MODE ACTIVATED. Let's get it. 💪"

### User selects **low-sodium** filter
- **emotion:** `cool`
- **message:** "Heart health check. Sodium: contained. Blood pressure: chill. 😎"

### User opens **Diet** filter (vegetarian/vegan/keto…)
- **emotion:** `thinking`
- **message:** "Sticking to your principles? I respect that energy."

### User selects **Vegetarian**
- **emotion:** `happy`
- **message:** "Fellow plant-based friend! 🌿 (I am literally a plant.)"

### User selects **Vegan**
- **emotion:** `cheer`
- **message:** "Full vegan mode! No animals harmed, maximum vegetables consumed. That's the way."

### User selects **Keto**
- **emotion:** `cool`
- **message:** "Fat as fuel. Big brain carb-free energy. Keto Mac respects it. 🥑"

### User opens **Rating** filter
- **emotion:** `cool`
- **message (rotate):**
  - "Looking for something that doesn't disappoint, eh? High standards! ⭐"
  - "Only the best-rated places? I like the way you think."

### User sets rating ≥ 4.5
- **emotion:** `cheer`
- **message:** "4.5 stars minimum? You are NOT settling. Legendary behaviour."

### User sets rating ≥ 3.5
- **emotion:** `thinking`
- **message:** "3.5+ stars. Reasonable. Pragmatic. I respect the balanced approach."

### User opens **Distance** filter
- **emotion:** `thinking`
- **message (rotate):**
  - "Close by or worth the walk? I say walk — burns off dinner before you even eat it."
  - "Every step to the restaurant is a free warm-up. Just saying. 🚶"

### User sets distance < 1 km
- **emotion:** `sleep`
- **message:** "500 m away? That's basically your kitchen. Cozy. 🏠"

### User sets distance > 5 km
- **emotion:** `excited`
- **message:** "5 km?! That's basically a hike AND dinner. You're incredible. 🏃"

### Crawl banner appears (new data loading)
- **emotion:** `excited`
- **message:** "Ooh, I'm fetching fresh data for you! Give me a sec… 🔍"

---

## 3 · Restaurant Detail Page

### Opening a restaurant page
- **emotion:** `idle`
- **message:** `null` *(quiet, let user browse)*

### Restaurant has 4.5+ rating
- **emotion:** `happy`
- **message:** "Highly rated! People are seriously into this place. 🌟"

### Restaurant has 10+ diet labels matching user prefs
- **emotion:** `cheer`
- **message:** "This place checks ALL your boxes. Almost suspicious how perfect it is."

### Viewing a low-calorie dish (< 400 kcal)
- **emotion:** `happy`
- **message (rotate):**
  - "Under 400 kcal? Your future self is writing you a thank-you note. 📝"
  - "Light and satisfying — that combo is *chef's kiss*."

### Viewing a high-calorie dish (> 900 kcal)
- **emotion:** `sweat`
- **message (rotate):**
  - "That's… a lot of energy. You'll need a very long walk after this. 😅"
  - "900+ kcal? Okay but you better enjoy every bite."
  - "Treat yourself! (But maybe also have a salad tomorrow.)"

### Viewing a dish with allergen warning matching user prefs
- **emotion:** `sweat`
- **message:** "⚠️ Heads up! This one contains something you wanted to avoid. Be careful!"

### Viewing a dish matching all user diet filters
- **emotion:** `happy`
- **message:** "This dish fits your profile perfectly. It was meant to be. 🍽️"

### Restaurant has 1–2 price level (cheap)
- **emotion:** `cheer`
- **message:** "Budget-friendly AND delicious? Mac approves. 💰"

### Restaurant has 4 price level (expensive)
- **emotion:** `cool`
- **message:** "Fancy night out? You deserve it. Order the good stuff."

---

## 4 · Diet Log Page

### No entries today
- **emotion:** `thinking`
- **message (morning, before 11am):** "Good morning! Start the day by logging breakfast. Mac is watching. 👀"
- **message (afternoon):** "Still haven't logged anything today. Busy? Hungry? Both?"
- **message (evening):** "Dinner time and nothing logged yet. It's never too late to start. 🌙"

### First food log of the day
- **emotion:** `cheer`
- **message:** "First log of the day! You've started — that's the hardest part. Let's keep going! 🎉"

### Very first log ever (new user)
- **emotion:** `cheer`
- **message:** "Your FIRST diet log! This is a historic moment. Welcome to healthy tracking! 🥦🎊"

### Calorie goal < 50% reached (under-eating warning)
- **emotion:** `sweat`
- **message (after 2pm):** "You've barely eaten today. Please eat! Even I'm worried and I'm a broccoli."

### Calorie goal 80–100% reached
- **emotion:** `happy`
- **message (rotate):**
  - "Almost at your goal! One more balanced meal and you nailed it. 💪"
  - "Looking good! Consistent days like this add up to big results."

### Calorie goal hit exactly (100%)
- **emotion:** `excited`
- **message:** "GOAL HIT! You landed exactly on your calorie target. That's basically sorcery. ✨"

### Calorie goal exceeded by < 10%
- **emotion:** `cool`
- **message:** "Slightly over. No stress — one meal doesn't define you. Balance tomorrow. 😎"

### Calorie goal exceeded by > 20%
- **emotion:** `sweat`
- **message (rotate):**
  - "Okay, we went a little over today. Tomorrow is a fresh start — I believe in you! 💪"
  - "That was a feast. Worth it? I hope so. Log a walk maybe? 🚶"

### Protein goal hit
- **emotion:** `excited`
- **message:** "Protein goal smashed! Your muscles are literally growing as we speak. 💪"

### Low-calorie meal logged (< 400 kcal)
- **emotion:** `happy`
- **message:** "Light meal logged! You're glowing with health right now. Trust me, I can tell."

### Oily / high-fat meal logged (fat > 35g in one meal)
- **emotion:** `sweat`
- **message (rotate):**
  - "Sweating just thinking about that fat content… but hey, no judgement. 😅"
  - "That one was rich. Balance it out with something green later? 🥦"

### 7-day logging streak
- **emotion:** `cheer`
- **message:** "7 days in a row! You're officially consistent. That's the hardest thing in health. 🔥"

### 30-day logging streak
- **emotion:** `cheer`
- **message:** "30 DAYS STRAIGHT. You are an absolute legend. Mac is proud. 🥦🏆"

---

## 5 · Saved Restaurants Page

### No saved restaurants yet
- **emotion:** `thinking`
- **message:** "No favourites yet! Find somewhere you love and hit that heart button. 💚"

### First restaurant saved
- **emotion:** `cheer`
- **message:** "Your first save! Building a little personal foodie map. I love this for you. ❤️"

### 5+ restaurants saved
- **emotion:** `cool`
- **message:** "Five favourites! You have taste. Literally and figuratively. 😎"

---

## 6 · Profile / Preferences Page

### Visiting profile for the first time (no prefs set)
- **emotion:** `thinking`
- **message:** "Set your preferences and I'll make much better suggestions! Takes 30 seconds. ⚙️"

### After saving preferences
- **emotion:** `cheer`
- **message:** "Preferences saved! Now I know exactly how to help you eat well. Let's go! 🥦"

### Allergy added
- **emotion:** `happy`
- **message:** "Allergy noted! I'll watch out for that on every page. Your safety matters. 🛡️"

### Daily goals set to weight-loss preset
- **emotion:** `cool`
- **message:** "Weight loss mode. Consistent deficit, balanced meals. You've got this. 💪"

### Daily goals set to muscle-gain preset
- **emotion:** `excited`
- **message:** "MUSCLE GAIN MODE. Eat big, lift heavy, sleep well. Mac's got your back. 🏋️"

---

## 7 · Inactivity & Idle States

| Idle time | emotion | message |
|-----------|---------|---------|
| 2 min | `sleep` | "Still there? I'm taking a little nap. Tap me if you need anything. 😴" |
| 5 min | `sleep` | "Zzz… the restaurants aren't going anywhere. Come back when you're ready. 🥦💤" |
| 10 min | `sleep` | "I've been asleep so long I dreamed I was a stir fry. Wake me up. 😂" |

---

## 8 · Time-of-Day Greetings (Home Page)

| Time | emotion | message |
|------|---------|---------|
| 6–9 am  | `happy`   | "Good morning! Breakfast is the most important meal. But you know that. 🌅" |
| 9–11 am | `idle`    | "Late breakfast or early lunch? No judgement from Mac. 🥦" |
| 12–2 pm | `excited` | "Lunch time! The best part of the workday. Let's find you something great. 🍽️" |
| 2–5 pm  | `cool`    | "Afternoon slump? A good snack fixes everything. 🍎" |
| 6–8 pm  | `happy`   | "Dinner o'clock! You've earned a proper meal. 🌇" |
| 8–11 pm | `thinking`| "Late dinner? Let's at least make it a good one. Nothing too heavy." |
| 11–5 am | `sleep`   | "It's late… are you really ordering now? I respect the commitment. 🌙" |

---

## 9 · Interaction Rules

| Rule | Detail |
|------|--------|
| **Frequency** | Max 1 message per 45 seconds; don't spam |
| **Dismissal** | User can close Mac; remember for the session |
| **Re-open** | Floating broccoli button stays; click to bring Mac back |
| **Priority** | Allergen warnings always override idle/fun messages |
| **No repeats** | Track last 3 messages shown; don't show same one twice in a row |
| **Tone** | Friendly, light, never guilt-trip — even on high-cal meals |
| **Goal** | Motivate, not shame. Celebrate small wins loudly. |

---

## 10 · Mac's Personality in One Line

> "I'm the friend who quietly makes sure you're eating well, celebrates every win, and absolutely will not let you feel bad about pizza."
