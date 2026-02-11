# Caduceus-Flux Frontend

Modern, responsive React frontend for the Caduceus-Flux Network Emulation Platform with full dark mode and multi-language support.

## Features

### 🎨 Modern UI Design
- **Dark/Light Theme**: Seamless theme switching with system preference detection
- **Responsive Design**: Optimized for desktop, tablet, and mobile devices
- **Modern Components**: Pre-built components with consistent styling
- **Smooth Animations**: Polished transitions and hover effects

### 🌍 Multi-Language Support
- **5 Languages**: English, Spanish, German, French, Turkish
- **Easy Extension**: Add new languages by creating translation files
- **Persistent Selection**: Language preference saved in localStorage
- **Real-time Switching**: Change language without page reload

### 🧩 Component Library

#### Core Components
- `MetricCard`: Display metrics with trends and icons
- `ModernButton`: Customizable button with variants and loading states
- `ModernCard`: Card container with hover effects
- `ModernInput`: Styled input fields with labels and validation
- `StatusBadge`: Status indicators with icons
- `ThemeSwitcher`: Toggle between light and dark modes
- `LanguageSwitcher`: Dropdown language selector

#### Styling Utilities
Pre-built Tailwind CSS classes for consistent styling:
- `.card`: Full-featured card with shadow and hover effects
- `.card-compact`: Compact card variant
- `.btn-primary`: Primary action button
- `.btn-secondary`: Secondary action button
- `.btn-danger`: Danger action button
- `.input-field`: Styled input field
- `.badge-*`: Status badges (success, warning, error, info)

## Installation

```bash
npm install
```

## Development

```bash
npm run dev
```

## Build

```bash
npm run build
```

## Usage Examples

### Theme Context

```tsx
import { useTheme } from './contexts/ThemeContext'

function MyComponent() {
  const { theme, toggleTheme, setTheme } = useTheme()
  
  return (
    <button onClick={toggleTheme}>
      Current theme: {theme}
    </button>
  )
}
```

### Translations

```tsx
import { useTranslation } from 'react-i18next'

function MyComponent() {
  const { t, i18n } = useTranslation()
  
  return (
    <div>
      <h1>{t('home.welcome')}</h1>
      <button onClick={() => i18n.changeLanguage('es')}>
        Español
      </button>
    </div>
  )
}
```

### Modern Components

```tsx
import { ModernButton } from '@components/ModernButton'
import { ModernCard } from '@components/ModernCard'
import { MetricCard } from '@components/MetricCard'
import { StatusBadge } from '@components/StatusBadge'
import { Activity } from 'lucide-react'

function Dashboard() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <MetricCard
        icon={<Activity className="w-5 h-5" />}
        label="Active Nodes"
        value={42}
        trend={12.5}
        color="blue"
      />
      
      <ModernCard padding="lg">
        <h3 className="text-lg font-semibold mb-4">Network Status</h3>
        <StatusBadge status="running" />
        <ModernButton variant="primary" fullWidth className="mt-4">
          View Details
        </ModernButton>
      </ModernCard>
    </div>
  )
}
```

## Adding New Languages

1. Create a new translation file in `src/i18n/locales/`:

```json
// src/i18n/locales/ja.json
{
  "app": {
    "name": "Caduceus-Flux",
    "tagline": "ネットワークエミュレーションプラットフォーム"
  },
  // ... other translations
}
```

2. Import and add to i18n config:

```typescript
// src/i18n/config.ts
import ja from './locales/ja.json'

i18n.init({
  resources: {
    // ... existing languages
    ja: { translation: ja },
  },
})
```

3. Add to language switcher:

```typescript
// src/components/LanguageSwitcher.tsx
const languages = [
  // ... existing languages
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
]
```

## Dark Mode

The application automatically detects system theme preference on first load. Users can override this with the theme switcher in the navigation bar.

Theme preference is persisted in localStorage and applied on subsequent visits.

## Project Structure

```
src/
├── components/         # Reusable UI components
│   ├── MetricCard.tsx
│   ├── ModernButton.tsx
│   ├── ModernCard.tsx
│   ├── ModernInput.tsx
│   ├── StatusBadge.tsx
│   ├── ThemeSwitcher.tsx
│   └── LanguageSwitcher.tsx
├── contexts/          # React contexts
│   └── ThemeContext.tsx
├── i18n/              # Internationalization
│   ├── config.ts
│   └── locales/
│       ├── en.json
│       ├── es.json
│       ├── de.json
│       ├── fr.json
│       └── tr.json
├── pages/             # Page components
├── services/          # API services
├── hooks/             # Custom hooks
├── types/             # TypeScript types
└── utils/             # Utility functions
```

## Design System

### Color Palette

The design system uses Tailwind CSS with custom color scales optimized for both light and dark modes:

- **Primary**: Blue (interactive elements)
- **Success**: Green (positive states)
- **Warning**: Yellow (cautionary states)
- **Error**: Red (error states)
- **Info**: Blue (informational states)

### Typography

- **Headings**: Bold, clear hierarchy
- **Body**: Regular weight for readability
- **Code**: Monospace font for technical content

### Spacing

Consistent spacing scale using Tailwind's default spacing:
- `gap-2`, `gap-4`, `gap-6`, `gap-8` for component spacing
- `p-4`, `p-6`, `p-8` for padding
- `rounded-xl`, `rounded-2xl` for border radius

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Performance

- Code splitting with React lazy loading
- Optimized bundle size
- Efficient re-renders with React.memo
- Debounced API calls

## License

Part of the Caduceus-Flux Network Emulation Platform

