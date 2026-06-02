import { create } from 'zustand'
import type { MacEmotion } from '@/components/mascot/MacMascot'

type Msg = { e: MacEmotion; t: string }

// ── Message pools ─────────────────────────────────────────────────────────────
const POOL: Record<string, Msg[]> = {
  greet_morning: [
    { e: 'happy',  t: "Good morning! Breakfast is the most important meal. But you know that. 🌅" },
    { e: 'cheer',  t: "Rise and shine! Let's find you a great start to the day. 🥦" },
    { e: 'happy',  t: "Morning! You're up early. That already makes you healthier than yesterday. 💪" },
  ],
  greet_noon: [
    { e: 'excited', t: "Lunch time! The best part of the workday. Let's find something great. 🍽️" },
    { e: 'happy',   t: "It's lunchtime! I've got opinions on where to eat. Let me help. 🥦" },
    { e: 'cool',    t: "Midday fuel incoming. Choose wisely and your afternoon will be unstoppable." },
  ],
  greet_evening: [
    { e: 'happy',  t: "Dinner o'clock! You've earned a proper meal today. 🌇" },
    { e: 'idle',   t: "Evening! Let's find something cosy and delicious for dinner." },
    { e: 'cool',   t: "Good evening. I know just the kind of place you need right now. 😎" },
  ],
  greet_night: [
    { e: 'sleep',    t: "Late night run? I respect the dedication. Keep it light though. 🌙" },
    { e: 'thinking', t: "It's late… let's keep it light. Your sleep will thank you." },
    { e: 'cool',     t: "Night owl mode. I'm always here. Let's find you something. 🌙" },
  ],

  idle_2min: [
    { e: 'sleep', t: "Psst… I'm napping. Tap me when you're hungry. 😴" },
    { e: 'sleep', t: "Still browsing? I'll just close my eyes for a bit… 💤" },
    { e: 'sleep', t: "You've been quiet. Taking a power nap. Wake me up when you're ready. 😴" },
  ],
  idle_5min: [
    { e: 'sleep', t: "Zzz… I dreamed I was a stir fry. Come back when you're hungry. 🥦💤" },
    { e: 'sleep', t: "Five minutes of silence. This is fine. I'm fine. Everything's fine. 😴" },
    { e: 'sleep', t: "The restaurants aren't going anywhere. Neither am I. Zzzz. 💤" },
  ],

  route_home: [
    { e: 'thinking', t: "Hmm, what are we craving today? 🤔" },
    { e: 'happy',    t: "Let me know your diet and I'll find you something good!" },
    { e: 'idle',     t: "I've got opinions on where to eat. Just saying. 🥦" },
  ],
  route_search: [
    { e: 'thinking', t: "I think you should eat a salad today. Just a vibe I'm getting." },
    { e: 'happy',    t: "Let's find you something delicious AND nutritious! 🔍" },
    { e: 'cool',     t: "Search mode activated. I'll keep an eye on the nutrition. 😎" },
  ],
  route_diet: [
    { e: 'happy',    t: "Diet tracker! This is where healthy habits are born. 📊" },
    { e: 'thinking', t: "How are those macros looking today? Let's check. 🥦" },
    { e: 'cheer',    t: "Logging your meals? You're already ahead of most people. Keep it up!" },
  ],
  route_saved: [
    { e: 'happy',    t: "Your favourite spots! Clearly a person of taste. ❤️" },
    { e: 'thinking', t: "Revisiting old favourites? Nothing wrong with a reliable classic." },
    { e: 'cool',     t: "Your curated food list. Exclusive. Refined. Just like you. 😎" },
  ],
  route_profile: [
    { e: 'thinking', t: "Set your preferences and I'll make much smarter suggestions! ⚙️" },
    { e: 'happy',    t: "Profile time! Tell me what you like and I'll handle the rest. 🥦" },
    { e: 'idle',     t: "Fine-tuning your health settings. I appreciate the attention to detail." },
  ],

  search_many: [
    { e: 'happy',  t: "Plenty of options! I believe in your ability to choose well. 🥦" },
    { e: 'cheer',  t: "Loads to pick from! This is a good problem to have. 🎉" },
    { e: 'happy',  t: "Look at all those choices. Something delicious is waiting for you!" },
  ],
  search_few: [
    { e: 'thinking', t: "Only a few results. You're either very specific or very healthy. Respect." },
    { e: 'thinking', t: "Slim pickings today. Try loosening a filter to see more options." },
    { e: 'cool',     t: "Quality over quantity. A few great options is all you need. 😎" },
  ],
  search_none: [
    { e: 'sweat',    t: "Nothing! Try fewer filters — or just move somewhere with better food. 😅" },
    { e: 'sweat',    t: "Hmm, no matches. These filters might be too strict for this area!" },
    { e: 'thinking', t: "Zero results. Let's try widening the search a bit. I believe in this city." },
  ],

  filter_lowfat: [
    { e: 'happy', t: "Low-fat filter on! Your arteries are literally applauding right now. 👏" },
    { e: 'cool',  t: "Cutting the fat. Smart and delicious — not a contradiction at all. 💙" },
  ],
  filter_lowsugar: [
    { e: 'happy',    t: "No sugar rush, no crash. Smooth brain energy all day. 🧠" },
    { e: 'thinking', t: "Low sugar. Your future self is already writing you a thank-you note." },
  ],
  filter_lowsodium: [
    { e: 'cool',  t: "Heart health check. Sodium: contained. Blood pressure: chill. 😎" },
    { e: 'happy', t: "Low sodium mode. Your heart is literally asking nicely. 🫀" },
  ],
  filter_highprotein: [
    { e: 'excited', t: "GAINS MODE ACTIVATED. Let's find that protein! 💪" },
    { e: 'cheer',   t: "High protein? Your muscles are already feeling it. LET'S GO! 🏋️" },
  ],
  filter_vegan: [
    { e: 'cheer', t: "Full vegan mode! Maximum vegetables. That's literally my language. 🌿" },
    { e: 'happy', t: "Fellow plant-based friend! (I am literally a plant, so I respect this.) 🥦" },
  ],
  filter_vegetarian: [
    { e: 'happy', t: "Vegetarian! Great choice for the planet AND your health. 🥗" },
    { e: 'cool',  t: "Keeping it plant-forward. Classy and delicious. 😎" },
  ],
  filter_keto: [
    { e: 'cool',     t: "Fat as fuel. Big brain, carb-free energy. Mac respects the keto grind. 🥑" },
    { e: 'thinking', t: "Keto mode. No bread? No problem. There's still so much to eat." },
  ],
  filter_halal: [
    { e: 'happy', t: "Halal filter on. Finding you trusted options right now. ☪️" },
    { e: 'idle',  t: "Halal certified spots incoming. Quality AND peace of mind. 🌟" },
  ],
  filter_rating_high: [
    { e: 'cheer',    t: "4.5 stars minimum?! You are NOT settling today. Legendary behaviour. ⭐" },
    { e: 'cool',     t: "Only the best-rated places? I like the way you think. 😎" },
    { e: 'thinking', t: "Looking for something that doesn't disappoint, eh? High standards!" },
  ],
  filter_generic: [
    { e: 'happy',    t: "Filtering for the good stuff! Your future self approves." },
    { e: 'thinking', t: "Sticking to your principles? I respect that energy." },
    { e: 'cool',     t: "Refining the search. Precision eating. I like it." },
  ],

  diet_first_log_ever: [
    { e: 'cheer', t: "Your FIRST diet log! This is a historic moment. Welcome to healthy tracking! 🎊" },
    { e: 'cheer', t: "You logged your first meal! The journey of a thousand healthy bites begins now. 🥦🎉" },
  ],
  diet_first_log_today: [
    { e: 'happy',  t: "First log of the day! Starting is the hardest part — you did it. 🥦" },
    { e: 'cheer',  t: "Day started! One meal logged. Let's keep the momentum going. 💪" },
    { e: 'idle',   t: "Nice, you've started tracking today! Keep it up and hit those goals." },
  ],
  diet_goal_hit: [
    { e: 'excited', t: "CALORIE GOAL HIT! You landed perfectly on target. That's basically sorcery! ✨" },
    { e: 'cheer',   t: "Goal reached! Consistent days like today add up to BIG results. 🏆" },
    { e: 'excited', t: "NAILED IT! Exactly on your calorie goal. Mac is doing a victory dance. 🥦💃" },
  ],
  diet_over: [
    { e: 'cool',  t: "Slightly over today. No stress — one meal doesn't define you. Balance tomorrow. 😎" },
    { e: 'sweat', t: "We went a little over. Tomorrow's a fresh start. Still proud of you for logging it! 💪" },
    { e: 'sweat', t: "Over budget today. But hey — at least you know. That's already half the battle." },
  ],
  diet_highfat: [
    { e: 'sweat', t: "Sweating just thinking about that fat content… no judgement! Maybe a walk later? 😅" },
    { e: 'sweat', t: "Rich meal logged! Hope it was worth every bite. Balance it out with something green. 🥗" },
  ],
  diet_lowcal: [
    { e: 'happy', t: "Light and balanced — your body loves you right now. ✨" },
    { e: 'happy', t: "Under 400 kcal! Your future self is writing you a thank-you note. 📝" },
    { e: 'cool',  t: "Lean meal. Efficient. Classy. Just like you. 😎" },
  ],
  diet_protein_goal: [
    { e: 'excited', t: "Protein goal smashed! Your muscles are literally growing as we speak. 💪" },
    { e: 'cheer',   t: "PROTEIN TARGET HIT! That's how gains are made. Mac approves. 🏋️" },
  ],

  prefs_saved: [
    { e: 'cheer', t: "Preferences saved! Now I know exactly how to help you eat well. Let's go! 🥦" },
    { e: 'happy', t: "All set! Your profile helps me give way smarter suggestions now. 🎯" },
    { e: 'cool',  t: "Locked in. I'll remember your preferences on every search. 😎" },
  ],
  first_save: [
    { e: 'cheer', t: "Your first saved restaurant! Building your personal foodie map. ❤️" },
    { e: 'happy', t: "Saved! The beginning of a beautiful collection. 🗺️" },
  ],

  // ── New filter reactions ────────────────────────────────────────────────────
  filter_allergy: [
    { e: 'happy',    t: "Allergy filter on! Keeping you safe. No sneaky ingredients on Mac's watch. 🛡️" },
    { e: 'cool',     t: "Noted. That ingredient is now on the no-go list. Safety first, always. 😎" },
    { e: 'happy',    t: "Smart filtering! Life's too short to worry about surprise allergens. ✅" },
    { e: 'thinking', t: "Allergy filter active. I'll flag anything suspicious. Trust me. 👀" },
  ],
  filter_nospicy: [
    { e: 'cool',     t: "No spice? Completely valid. Not everyone has a fire-breathing constitution. 🧊" },
    { e: 'happy',    t: "Mild mode activated. Comfort food hits different when your mouth isn't burning. 😌" },
    { e: 'thinking', t: "Spice-free. Your taste buds, your rules. I respect it. 🌶️🚫" },
  ],
  filter_sort_distance: [
    { e: 'thinking', t: "Sorted by distance! The closest restaurant is the one you'll actually visit. 📍" },
    { e: 'cool',     t: "Near me mode! Every step to the restaurant is a free warm-up. 🚶" },
    { e: 'happy',    t: "Closest first! Sometimes convenience IS the most nutritious choice. 🏃" },
  ],
  filter_sort_price: [
    { e: 'cool',     t: "Cheapest first! Eating well on a budget is a skill. Mac respects the hustle. 💰" },
    { e: 'happy',    t: "Budget mode! Great food doesn't always mean expensive food. Hidden gems ahead. 💎" },
    { e: 'thinking', t: "Sorted by price. Smart money + good food = the ultimate combo. 🧠" },
  ],
  filter_calorie: [
    { e: 'happy',    t: "Calorie range set! Mindful eating is the real superpower. 📊" },
    { e: 'cool',     t: "Precision calorie targeting. You know exactly what you want. I like that. 🎯" },
    { e: 'thinking', t: "Tracking calories? Awareness is 80% of the battle. You're already winning. 💪" },
  ],

  // ── Tap (click Mac directly) ────────────────────────────────────────────────
  tap: [
    { e: 'excited',  t: "Oh! You tapped me! I wasn't expecting that — but I love the attention. 👆" },
    { e: 'happy',    t: "Hey! Since you're here… have you had vegetables today? Asking for a friend. 🥦" },
    { e: 'cool',     t: "You rang? Mac is at your service. Ready when you are. 🫡" },
    { e: 'thinking', t: "Fun fact: broccoli is technically a flower. Just letting you know. 🌸" },
    { e: 'excited',  t: "Tap! Feeling lucky? Search for something random today. I dare you. 🎲" },
    { e: 'cool',     t: "You tapped me. Interesting choice. I like your style. 😎" },
    { e: 'cheer',    t: "Tapped! Since you're here — today's quest: try a restaurant you've never visited. 🗺️" },
    { e: 'thinking', t: "Hmm. You tapped me. I'm choosing to feel flattered by this." },
    { e: 'sleep',    t: "I was literally sleeping and you— fine. I'm up. What do you need? 😤" },
    { e: 'happy',    t: "Did you know 'broccoli' comes from Italian for 'little arms'? I have arms! 💪" },
    { e: 'excited',  t: "Random quest: find the highest-rated place within 1 km and just go for it. ⭐" },
    { e: 'thinking', t: "Psst — when did you last try a new cuisine? Now might be the time. 🌍" },
    { e: 'cool',     t: "You clicked me. Bold. I like it. Want a recommendation? I'm full of them. 😎" },
    { e: 'happy',    t: "Hi! Your friendly neighbourhood broccoli is here. What are we eating today? 🥦" },
    { e: 'excited',  t: "Oh hey! Quick challenge: find a meal under 600 kcal that you'd actually enjoy. Go! 🎯" },
  ],

  // ── Periodic motivation (every few minutes) ─────────────────────────────────
  motivation: [
    { e: 'idle',     t: "Gentle reminder: drink some water. Yes, right now. I'll wait. 💧" },
    { e: 'thinking', t: "Quick tip: eat slowly and actually taste your food. Revolutionary, I know. 🍽️" },
    { e: 'cool',     t: "Consistency beats perfection. One good meal beats no meal. Keep going. 💪" },
    { e: 'happy',    t: "Reminder: you're doing better than you think. Logging food is already a win. 🥦" },
    { e: 'thinking', t: "Health tip: have at least one green thing in your next meal. (Pickles don't count.)" },
    { e: 'cool',     t: "Mini challenge: try a cuisine you haven't had in the last 30 days. 🌍" },
    { e: 'idle',     t: "The best time to eat well was yesterday. The second best time is right now." },
    { e: 'thinking', t: "Eating a variety of colours = a variety of nutrients. Be colourful! 🌈" },
    { e: 'happy',    t: "You've been making healthy choices today. I see it. Keep going. 🥦✨" },
    { e: 'cool',     t: "Tip: prep ONE healthy thing for the week. Just one. You can do that. 📦" },
    { e: 'thinking', t: "Hydration check! Seriously though. When did you last drink water? Go. 💧" },
    { e: 'idle',     t: "Small wins add up. One logged meal → one healthy habit → one better you." },
    { e: 'happy',    t: "This is your sign to take a 5-minute walk after your next meal. Your gut will love it. 🚶" },
    { e: 'cool',     t: "Fun nutrition fact: protein keeps you full longer than carbs. Snack accordingly. 💪" },
  ],

  // ── More quest variety ────────────────────────────────────────────────────────
  quest: [
    { e: 'cool',     t: "Today's quest: pick a restaurant 1 km further than usual and walk there. 🚶" },
    { e: 'thinking', t: "Challenge: eat a meal with 30g+ protein today. Your muscles will thank you. 💪" },
    { e: 'cool',     t: "Feeling adventurous? Try a cuisine you've never logged before today! 🌍" },
    { e: 'happy',    t: "Why not go low-sodium today? Your heart is quietly asking. 🫀" },
    { e: 'thinking', t: "Mini goal: hit your protein target AND stay under calories today. 🎯" },
    { e: 'cool',     t: "Find the highest-rated restaurant within 1 km and treat yourself. ⭐" },
    { e: 'thinking', t: "Don't be a couch potato — find somewhere further and walk there. 🥔➡️🚶" },
    { e: 'excited',  t: "Quest: eat a meal with all three macros — protein, fat, carbs. Balance is key! ⚖️" },
    { e: 'happy',    t: "Goal: discover a NEW restaurant this week. Your food map should always grow. 🗺️" },
    { e: 'cool',     t: "Challenge: no processed food for ONE meal. Just one. Fresh and real. 🥗" },
    { e: 'excited',  t: "Bonus quest: find a 4.8+ star restaurant and treat yourself. You've earned it. ⭐⭐" },
    { e: 'thinking', t: "Try eating at a time you normally skip a meal. Meal timing actually matters. ⏰" },
    { e: 'happy',    t: "Quest: find a meal that costs under HK$50 AND tastes amazing. They exist! 💰" },
    { e: 'cool',     t: "Today's vibe: find somewhere new, order something you've never tried. Report back. 🧪" },
  ],
}

// ── Store ─────────────────────────────────────────────────────────────────────

interface MacState {
  emotion: MacEmotion
  message: string | null
  closed: boolean
  _lastAt: number
  _recent: string[]
}

interface MacActions {
  tryShow: (poolKey: string, priority?: boolean) => void
  tap: () => void
  dismiss: () => void
  close: () => void
  reopen: () => void
}

export const useMacStore = create<MacState & MacActions>((set, get) => ({
  emotion: 'idle',
  message: null,
  closed: false,
  _lastAt: 0,
  _recent: [],

  tryShow(poolKey, priority = false) {
    const pool = POOL[poolKey]
    if (!pool?.length) return
    const s = get()
    if (s.closed) return
    if (!priority && Date.now() - s._lastAt < 30_000) return
    const available = pool.filter(m => !s._recent.includes(m.t))
    const src = available.length ? available : pool
    const pick = src[Math.floor(Math.random() * src.length)]
    set({
      emotion: pick.e,
      message: pick.t,
      _lastAt: Date.now(),
      _recent: [pick.t, ...s._recent].slice(0, 4),
    })
  },

  tap()     { get().tryShow('tap', true) },
  dismiss() { set({ message: null }) },
  close()   { set({ closed: true, message: null }) },
  reopen()  { set({ closed: false }) },
}))

/** Trigger Mac from any component without needing the hook. */
export function notifyMac(poolKey: string, priority = false) {
  useMacStore.getState().tryShow(poolKey, priority)
}
