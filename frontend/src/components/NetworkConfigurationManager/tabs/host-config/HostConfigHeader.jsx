// HostConfigHeader.jsx - Header component with apply button
import React from 'react';
import { Monitor, Save } from 'lucide-react';
import ActionButton from '../../components/ActionButton';

export const HostConfigHeader = ({ selectedNode, loading, onApplyConfiguration }) => {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="p-3 bg-blue-600 text-white rounded-2xl shadow">
          <Monitor size={18} />
        </div>
        <div>
          <h2 className="text-xl font-bold text-gray-900">Configure Host</h2>
          <p className="text-gray-600">{selectedNode.id}</p>
        </div>
      </div>
      <ActionButton
        onClick={onApplyConfiguration}
        loading={loading}
        icon={<Save size={16} />}
        label="Apply Configuration"
      />
    </div>
  );
};