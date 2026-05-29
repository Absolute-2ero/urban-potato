import { Button, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { PRIMARY_COLOR } from '@/constants'

const { Title, Text, Paragraph } = Typography

const FEATURES = [
  {
    emoji: '🔍',
    title: 'Diet-aware search',
    desc: 'Find restaurants matching your dietary needs — vegan, halal, gluten-free, and more. Search by dish name, cuisine, or filter by label.',
    bg: '#E8F5E9', accent: '#2D9B5A',
  },
  {
    emoji: '⚠️',
    title: 'Allergen alerts',
    desc: 'Real-time allergen warnings so you never have to guess what\'s in your food. Set your allergies once and we\'ll flag them everywhere.',
    bg: '#FFF0F0', accent: '#E85454',
  },
  {
    emoji: '📊',
    title: 'Nutrition tracking',
    desc: 'Log your meals, track calories and macros, and hit your daily goals. Set custom targets for calories, protein, fat, and carbs.',
    bg: '#E3F2FD', accent: '#1565C0',
  },
  {
    emoji: '✨',
    title: 'Personalised results',
    desc: 'Set your preferences once and every search automatically fits you. Matched dishes are highlighted so you spot them instantly.',
    bg: '#F3E5F5', accent: '#6A1B9A',
  },
]

export default function AboutPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  return (
    <div style={{ background: '#F7F3EE', minHeight: 'calc(100vh - 52px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 1 }}>

        {/* Hero */}
        <div style={{
          background: 'linear-gradient(150deg, #edfff4 0%, #F7F3EE 70%)',
          padding: '56px 24px 48px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>🥗</div>
          <Title level={1} style={{ margin: '0 0 10px', color: PRIMARY_COLOR, fontSize: 40, fontWeight: 800, letterSpacing: -1 }}>
            MacroBite
          </Title>
          <Paragraph style={{ color: '#6B7A7A', fontSize: 17, maxWidth: 520, margin: '0 auto 32px', lineHeight: 1.7 }}>
            MacroBite helps you find restaurants that actually fit your diet — whether you're vegan,
            avoiding allergens, hitting a protein goal, or just curious about what you're eating.
            Search any restaurant or cuisine, filter by your dietary needs, and track your daily
            nutrition all in one place.
          </Paragraph>

          {!user && (
            <Button
              type="primary" size="large"
              onClick={() => navigate('/login')}
              style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 999, padding: '0 36px', height: 46, fontSize: 15 }}
            >
              Get started — it's free
            </Button>
          )}
          {user && (
            <Button
              type="primary" size="large"
              onClick={() => navigate('/search')}
              style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 999, padding: '0 36px', height: 46, fontSize: 15 }}
            >
              Start searching →
            </Button>
          )}
        </div>

        {/* Feature cards */}
        <div style={{ maxWidth: 960, margin: '0 auto', padding: '48px 24px 56px' }}>
          <Text style={{
            fontSize: 11, color: '#AAB4B4', textTransform: 'uppercase',
            letterSpacing: 1.4, display: 'block', marginBottom: 20, fontWeight: 600, textAlign: 'center',
          }}>
            What MacroBite does
          </Text>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 16 }}>
            {FEATURES.map((f) => (
              <div key={f.title} style={{
                background: f.bg, borderRadius: 16, padding: '24px 20px',
                border: `1px solid ${f.accent}22`,
              }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>{f.emoji}</div>
                <Text strong style={{ color: f.accent, fontSize: 15, display: 'block', marginBottom: 8 }}>{f.title}</Text>
                <Text style={{ color: '#6B7A7A', fontSize: 13, lineHeight: 1.6 }}>{f.desc}</Text>
              </div>
            ))}
          </div>
        </div>

        {/* Sign-up nudge for guests */}
        {!user && (
          <div style={{
            background: `linear-gradient(135deg, ${PRIMARY_COLOR}10 0%, #E3F2FD20 100%)`,
            borderTop: '1px solid #E8E0D5', borderBottom: '1px solid #E8E0D5',
            padding: '40px 24px', textAlign: 'center',
          }}>
            <Title level={3} style={{ margin: '0 0 10px', color: '#1E2A2A' }}>
              Ready to eat smarter?
            </Title>
            <Text style={{ color: '#6B7A7A', fontSize: 15, display: 'block', marginBottom: 24 }}>
              Create a free account to save your preferences, track macros, and get personalised results.
            </Text>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Button
                type="primary" size="large"
                onClick={() => navigate('/login')}
                style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 999, padding: '0 32px' }}
              >
                Sign up — it's free
              </Button>
              <Button
                size="large"
                onClick={() => navigate('/search')}
                style={{ borderRadius: 999, padding: '0 32px' }}
              >
                Browse without account
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer style={{
        padding: '24px', textAlign: 'center',
        borderTop: '1px solid #E8E0D5', background: '#fff',
      }}>
        <Text type="secondary" style={{ fontSize: 13 }}>
          Made with ❤️ by students at Tsinghua University · Web Information Retrieval course
        </Text>
      </footer>
    </div>
  )
}
