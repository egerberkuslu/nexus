# Frontend Architecture

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── atoms/          # Basic building blocks
│   ├── molecules/      # Simple combinations
│   ├── organisms/      # Complex components
│   └── layouts/        # Layout components
├── features/           # Feature-based modules
│   ├── network/        # Network management feature
│   ├── topology/       # Topology feature
│   ├── monitoring/     # Monitoring feature
│   └── projects/       # Projects feature
├── pages/              # Page components
├── hooks/              # Custom React hooks
├── services/           # API and external services
├── store/              # State management
├── types/              # TypeScript types
├── utils/              # Utility functions
├── contexts/           # React contexts
└── i18n/              # Internationalization

## Design Principles

1. **Atomic Design**: Components organized by complexity
2. **Feature-based Architecture**: Related functionality grouped together
3. **Separation of Concerns**: Logic separated from presentation
4. **DRY (Don't Repeat Yourself)**: Reusable components and hooks
5. **Type Safety**: Full TypeScript coverage
6. **Performance**: Lazy loading, memoization, code splitting

## Component Hierarchy

### Atoms (Basic UI Elements)
- Button, Input, Badge, Icon, Text, etc.

### Molecules (Simple Combinations)
- FormField, Card, MetricDisplay, StatusIndicator, etc.

### Organisms (Complex Components)
- NetworkTable, TopologyCanvas, MonitoringDashboard, etc.

### Templates (Page Layouts)
- MainLayout, DashboardLayout, EditorLayout, etc.

## State Management

- **React Query**: Server state management
- **Zustand**: Client state management
- **Context API**: Theme, i18n, auth

## Code Standards

- **ESLint**: Code quality
- **Prettier**: Code formatting
- **TypeScript**: Type safety
- **Component naming**: PascalCase
- **File naming**: kebab-case for files, PascalCase for components

