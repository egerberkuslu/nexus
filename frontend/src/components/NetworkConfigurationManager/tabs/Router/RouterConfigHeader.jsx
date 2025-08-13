import React from 'react';
import { FiGitBranch, FiRefreshCcw, FiSave } from 'react-icons/fi';
import ActionButton from '../../components/ActionButton';

export function RouterConfigHeader({ 
  selectedNode, 
  loading, 
  applying, 
  onPreviewPlan, 
  onApplyConfiguration 
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="p-3 bg-gray-900 text-white rounded-2xl shadow">
          <FiGitBranch size={18} />
        </div>
        <div>
          <h2 className="text-xl font-bold text-gray-900">Configure Router</h2>
          <p className="text-gray-600">{selectedNode.id}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <ActionButton 
          onClick={onPreviewPlan} 
          loading={loading} 
          icon={<FiRefreshCcw size={16} />} 
          label="Dry‑Run Plan" 
          variant="secondary" 
        />
        <ActionButton 
          onClick={onApplyConfiguration} 
          loading={loading || applying} 
          icon={<FiSave size={16} />} 
          label="Apply Configuration" 
        />
      </div>
    </div>
  );
}