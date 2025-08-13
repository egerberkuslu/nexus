import React from 'react';

export function DryRunPlanPreview({ dryRun, planPreview, onHide }) {
  if (!dryRun) {
    return null;
  }

  return (
    <div className="bg-gray-50 rounded-lg p-4 border">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-gray-900">Dry‑Run Execution Plan</h4>
        <button className="text-sm text-blue-600 hover:underline" onClick={onHide}>
          Hide
        </button>
      </div>
      {planPreview.length === 0 ? (
        <div className="text-sm text-gray-600">No commands were generated.</div>
      ) : (
        <div className="space-y-1 text-xs font-mono">
          {planPreview.map((p, i) => (
            <div key={i} className="flex flex-wrap gap-2">
              <span className="px-2 py-0.5 rounded bg-gray-200 text-gray-800">{p.node}</span>
              <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700">{p.where}</span>
              <span className="break-all">{p.cmd}</span>
              {p.ignore_error ? (
                <span className="px-1 rounded bg-yellow-100 text-yellow-800">ignored</span>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}