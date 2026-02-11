import type { Dispatch, SetStateAction } from 'react'

import { Button } from '@/components/atoms/Button'

export type KvValueType = 'string' | 'number' | 'boolean' | 'json'

export type KvRow = {
  id: string
  key: string
  type: KvValueType
  value: string
}

export const newKvRow = (init?: Partial<Omit<KvRow, 'id'>>): KvRow => ({
  id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  key: init?.key ?? '',
  type: init?.type ?? 'string',
  value: init?.value ?? '',
})

export const kvRowsToObject = (rows: KvRow[]): { obj: Record<string, any>; errors: string[] } => {
  const obj: Record<string, any> = {}
  const errors: string[] = []
  for (const row of rows || []) {
    const key = (row.key || '').trim()
    if (!key) continue

    const raw = row.value ?? ''
    if (row.type === 'string') {
      obj[key] = raw
      continue
    }

    if (row.type === 'number') {
      const n = Number(raw)
      if (!Number.isFinite(n)) {
        errors.push(`${key}: not a number`)
        continue
      }
      obj[key] = n
      continue
    }

    if (row.type === 'boolean') {
      const v = String(raw).trim().toLowerCase()
      if (v !== 'true' && v !== 'false') {
        errors.push(`${key}: must be true/false`)
        continue
      }
      obj[key] = v === 'true'
      continue
    }

    try {
      obj[key] = JSON.parse(raw || 'null')
    } catch (e: any) {
      errors.push(`${key}: invalid JSON (${e?.message || 'parse error'})`)
    }
  }
  return { obj, errors }
}

export const kvObjectToRows = (value: any, typeHint: KvValueType = 'string'): KvRow[] => {
  if (!value || typeof value !== 'object') return [newKvRow({ type: typeHint })]
  const entries = Object.entries(value as Record<string, any>)
  if (!entries.length) return [newKvRow({ type: typeHint })]
  return entries.map(([k, v]) => {
    if (typeof v === 'boolean') return newKvRow({ key: k, type: 'boolean', value: String(v) })
    if (typeof v === 'number') return newKvRow({ key: k, type: 'number', value: String(v) })
    if (v && typeof v === 'object') return newKvRow({ key: k, type: 'json', value: JSON.stringify(v, null, 2) })
    return newKvRow({ key: k, type: 'string', value: String(v ?? '') })
  })
}

export function KvTableEditor({
  rows,
  setRows,
  keyPlaceholder = 'key',
  valuePlaceholder = 'value',
}: {
  rows: KvRow[]
  setRows: Dispatch<SetStateAction<KvRow[]>>
  keyPlaceholder?: string
  valuePlaceholder?: string
}) {
  return (
    <div className="space-y-2">
      <div className="overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr className="text-left">
              <th className="px-3 py-2 font-medium text-gray-700 dark:text-gray-200">Key</th>
              <th className="px-3 py-2 font-medium text-gray-700 dark:text-gray-200 w-32">Type</th>
              <th className="px-3 py-2 font-medium text-gray-700 dark:text-gray-200">Value</th>
              <th className="px-3 py-2 w-24" />
            </tr>
          </thead>
          <tbody>
            {(rows || []).map((r) => (
              <tr key={r.id} className="border-t border-gray-200 dark:border-gray-800">
                <td className="px-3 py-2 align-top">
                  <input
                    value={r.key}
                    onChange={(e) =>
                      setRows((prev) => prev.map((x) => (x.id === r.id ? { ...x, key: e.target.value } : x)))
                    }
                    placeholder={keyPlaceholder}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900"
                  />
                </td>
                <td className="px-3 py-2 align-top">
                  <select
                    value={r.type}
                    onChange={(e) =>
                      setRows((prev) => prev.map((x) => (x.id === r.id ? { ...x, type: e.target.value as KvValueType } : x)))
                    }
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900"
                  >
                    <option value="string">string</option>
                    <option value="number">number</option>
                    <option value="boolean">boolean</option>
                    <option value="json">json</option>
                  </select>
                </td>
                <td className="px-3 py-2 align-top">
                  {r.type === 'json' ? (
                    <textarea
                      value={r.value}
                      onChange={(e) =>
                        setRows((prev) => prev.map((x) => (x.id === r.id ? { ...x, value: e.target.value } : x)))
                      }
                      placeholder={valuePlaceholder}
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 font-mono text-xs"
                    />
                  ) : (
                    <input
                      value={r.value}
                      onChange={(e) =>
                        setRows((prev) => prev.map((x) => (x.id === r.id ? { ...x, value: e.target.value } : x)))
                      }
                      placeholder={valuePlaceholder}
                      className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900"
                    />
                  )}
                </td>
                <td className="px-3 py-2 align-top text-right">
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => setRows((prev) => (prev.length <= 1 ? prev : prev.filter((x) => x.id !== r.id)))}
                    disabled={(rows || []).length <= 1}
                  >
                    Remove
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex justify-end">
        <Button size="xs" variant="secondary" onClick={() => setRows((prev) => [...prev, newKvRow()])}>
          Add row
        </Button>
      </div>
    </div>
  )
}

