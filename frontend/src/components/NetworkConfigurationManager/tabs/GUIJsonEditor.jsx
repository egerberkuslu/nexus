import React, { lazy, Suspense, useMemo } from 'react';
import { Wand2 } from 'lucide-react';

// Lazy-load the editor
const JSONEdit = lazy(() =>
  import('json-edit-react').then(mod => ({ default: mod.JsonEditor }))
);

// Optional theme loader
const loadTheme = () =>
  import('json-edit-react').then(mod => mod.githubLightTheme || undefined);

export const GUIJsonEditor = ({
  value,
  onChange,
  headerHeight = 96,
}) => {
  const parsed = useMemo(() => {
    try { return JSON.parse(value || '{}'); } catch { return {}; }
  }, [value]);

  const handleChange = (...args) => {
    let nextData = args[0];
    if (typeof nextData !== 'object' || nextData === null) {
      const maybeFull = args[2];
      nextData = (maybeFull && typeof maybeFull === 'object') ? maybeFull : parsed;
    }
    try { onChange(JSON.stringify(nextData ?? {}, null, 2)); } catch {}
  };

  const formatPretty = () => {
    try { onChange(JSON.stringify(JSON.parse(value || '{}'), null, 2)); } catch {}
  };

  const isValid = useMemo(() => {
    try { JSON.parse(value || '{}'); return true; } catch { return false; }
  }, [value]);

  const editorHeight = `calc(100vh - ${headerHeight}px)`;

  return (
    <div
      className="w-full rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden flex flex-col"
      style={{ height: editorHeight }}
    >
      {/* Sticky Toolbar */}
     

      {/* Scrollable Editor */}
      <div className="flex-1 overflow-auto">
        <Suspense
          fallback={
            <div className="w-full h-full flex items-center justify-center text-slate-600 text-sm bg-slate-50">
              Loading editor…
            </div>
          }
        >
          <EditorInner parsed={parsed} onChange={handleChange} />
        </Suspense>
      </div>
    </div>
  );
};

const EditorInner = ({ parsed, onChange }) => {
  const [ThemeComp, setThemeComp] = React.useState();

  React.useEffect(() => {
    let alive = true;
    loadTheme().then((t) => { if (alive) setThemeComp(() => t); });
    return () => { alive = false; };
  }, []);

  return (
    <div className="w-full min-h-full">
      <JSONEdit
        data={parsed}
        onChange={onChange}
        rootName={false}
        className="w-full h-full"
        style={{
          width: '100%',
          minHeight: '100%',
          fontFamily:
            'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
          fontSize: 13,
          '--jer-bg': '#ffffff',
          '--jer-border-color': '#e2e8f0',
          '--jer-node-hover': '#f8fafc',
          '--jer-key-color': '#0f172a',
          '--jer-value-color': '#0b1324',
          '--jer-type-color': '#64748b',
          '--jer-accent': '#6366f1',
          '--jer-accent-contrast': '#ffffff',
          '--jer-badge-bg': '#ecfeff',
          '--jer-badge-fg': '#0891b2',
          '--jer-focus-ring': '#93c5fd',
          outline: 'none',
        }}
        theme={ThemeComp}
      />
    </div>
  );
};
