import { Button, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { PRIMARY_COLOR } from '@/constants'

const { Title, Text, Paragraph } = Typography

const FEATURES = [
  {
    emoji: '🔍',
    title: 'Diet-aware search',
    desc: 'Find restaurants matching your dietary needs — vegan, halal, gluten-free, and more. Filter by dish name, cuisine, or dietary label.',
    bg: '#E8F5E9', accent: '#2D9B5A',
  },
  {
    emoji: '⚠️',
    title: 'Allergen alerts',
    desc: 'Real-time allergen warnings on every restaurant. Set your allergies once and we\'ll flag them automatically.',
    bg: '#FFF0F0', accent: '#E85454',
  },
  {
    emoji: '📊',
    title: 'Nutrition tracking',
    desc: 'Log meals, track calories and macros, and hit your daily goals with custom targets for protein, fat, and carbs.',
    bg: '#E3F2FD', accent: '#1565C0',
  },
  {
    emoji: '✨',
    title: 'Personalised results',
    desc: 'Set your preferences once and every search fits you. Matched dishes are highlighted so you spot them instantly.',
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
          <Paragraph style={{ color: '#6B7A7A', fontSize: 17, maxWidth: 480, margin: '0 auto 32px', lineHeight: 1.7 }}>
            Find restaurants that actually fit your diet. Search by dish, filter by dietary needs, and track your daily nutrition — all in one place.
          </Paragraph>
          <Button
            type="primary" size="large"
            onClick={() => navigate(user ? '/search' : '/login')}
            style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 999, padding: '0 36px', height: 46, fontSize: 15 }}
          >
            {user ? 'Start searching →' : 'Get started — it\'s free'}
          </Button>
        </div>

        {/* Feature cards */}
        <div style={{ maxWidth: 960, margin: '0 auto', padding: '48px 24px 40px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
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

        {/* Nutrition data disclaimer */}
        <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 24px 48px' }}>
          <div style={{
            background: '#FFFBEB', borderRadius: 12,
            border: '1px solid #FDE68A', padding: '20px 24px',
            display: 'flex', gap: 14, alignItems: 'flex-start',
          }}>
            <span style={{ fontSize: 22, flexShrink: 0 }}>🤖</span>
            <div>
              <Text strong style={{ fontSize: 14, color: '#92400E', display: 'block', marginBottom: 4 }}>
                About nutrition data
              </Text>
              <Text style={{ fontSize: 13, color: '#78716C', lineHeight: 1.6 }}>
                Calorie, macro, and dietary label data for menu items is estimated using AI language models
                based on dish names and descriptions. These are approximations and may not reflect the
                actual nutritional content of your meal. Always consult the restaurant or a registered
                dietitian for precise dietary advice.
              </Text>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer style={{
        padding: '24px', textAlign: 'center' as const,
        borderTop: '1px solid #E8E0D5', background: '#fff',
      }}>
        <Text type="secondary" style={{ fontSize: 13 }}>
          Made with ❤️ by students at Tsinghua University · Web Information Retrieval course
        </Text>
      </footer>
    </div>
  )
}
