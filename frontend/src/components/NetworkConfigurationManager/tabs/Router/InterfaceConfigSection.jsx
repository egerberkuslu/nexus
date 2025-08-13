import React from 'react';
import { FiSettings, FiPlus } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';
import { InputField } from '../../components/FormComponents';

const DEFAULT_PREFIX = '24';

export function InterfaceConfigSection({ 
  local, 
  selectedNode, 
  sections, 
  dispatch, 
  onToggle,
  onInterfaceStructuralChange
}) {
  // Handle interface field changes
  const handleInterfaceFieldChange = (index, field, value) => {
    console.log('Interface field change:', { index, field, value });
    dispatch({ type: 'IF_SET', index, field, value });
  };

  // Handle interface removal with proper tracking
  const handleInterfaceRemove = (index) => {
    console.log('Removing interface at index:', index);
    
    // Call structural change callback BEFORE dispatching the removal
    if (onInterfaceStructuralChange) {
      onInterfaceStructuralChange();
    }
    
    // Instead of immediately removing, mark for deletion if it exists on the router
    const interfaceToRemove = local.interfaces[index];
    if (interfaceToRemove && interfaceToRemove.name) {
      // Check if this is an existing interface that needs to be deleted on the router
      if (interfaceToRemove.id && !interfaceToRemove.id.includes('new-')) {
        // Mark existing interface for deletion
        dispatch({ 
          type: 'IF_SET', 
          index, 
          field: 'operation', 
          value: 'delete' 
        });
        console.log('Marked interface for deletion:', interfaceToRemove.name);
      } else {
        // Remove new interface that hasn't been applied yet
        dispatch({ type: 'IF_RM', index });
        console.log('Removed new interface:', interfaceToRemove.name);
      }
    }
  };

  // Handle interface addition with proper tracking
  const handleInterfaceAdd = () => {
    console.log('Adding new interface for router:', selectedNode.id);
    
    // Call structural change callback BEFORE dispatching the addition
    if (onInterfaceStructuralChange) {
      onInterfaceStructuralChange();
    }
    
    dispatch({ type: 'IF_ADD', routerId: selectedNode.id });
  };

  // Filter out interfaces marked for deletion from display
  const visibleInterfaces = (local.interfaces || []).filter(intf => intf.operation !== 'delete');

  return (
    <ConfigSection 
      title="Interface Configuration" 
      icon={FiSettings} 
      expanded={sections.interfaces} 
      onToggle={() => onToggle('interfaces')}
    >
      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Network Interfaces</h4>
        
        {visibleInterfaces.map((intf, i) => {
          // Find original index in the full interfaces array
          const originalIndex = local.interfaces.findIndex(originalIntf => 
            originalIntf.id === intf.id || 
            (originalIntf.name === intf.name && originalIntf.operation !== 'delete')
          );
          
          return (
            <div key={intf.id || i} className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4 p-4 border rounded bg-white">
              <InputField 
                label="Interface Name" 
                value={intf.name || `${selectedNode.id}-eth${i}`} 
                onChange={(v) => handleInterfaceFieldChange(originalIndex, 'name', v)} 
                placeholder={`${selectedNode.id}-eth${i}`} 
              />
              <InputField 
                label="IP Address" 
                value={intf.ip || ''} 
                onChange={(v) => handleInterfaceFieldChange(originalIndex, 'ip', v)} 
                placeholder="10.0.0.1" 
              />
              <InputField 
                label="Prefix Length" 
                value={intf.prefix || DEFAULT_PREFIX} 
                onChange={(v) => handleInterfaceFieldChange(originalIndex, 'prefix', v)} 
                placeholder={DEFAULT_PREFIX} 
                type="number"
                min="0"
                max="32"
              />
              <div className="flex flex-col">
                <label className="text-sm font-medium text-gray-600 mb-1">Preview</label>
                <div className="p-2 bg-gray-50 rounded text-xs font-mono">
                  {intf.ip ? `${intf.ip}/${intf.prefix || DEFAULT_PREFIX}` : 'No IP configured'}
                </div>
              </div>
              <div className="flex flex-col">
                <label className="text-sm font-medium text-gray-600 mb-1">Actions</label>
                <button 
                  onClick={() => handleInterfaceRemove(originalIndex)} 
                  className="p-2 text-red-600 hover:bg-red-50 rounded border" 
                  title="Remove interface"
                >
                  Remove
                </button>
              </div>
            </div>
          );
        })}
        
        <button 
          onClick={handleInterfaceAdd} 
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <FiPlus size={16} /> Add Interface
        </button>
      </div>

      {/* Show pending deletions */}
      {local.interfaces?.some(intf => intf.operation === 'delete') && (
        <div className="mb-4 p-3 bg-red-50 rounded border border-red-200">
          <h5 className="font-medium text-red-800 mb-2">Pending Interface Deletions</h5>
          <div className="space-y-1">
            {local.interfaces
              .filter(intf => intf.operation === 'delete')
              .map((intf, i) => (
                <div key={i} className="text-sm text-red-700 font-mono">
                  • {intf.name} will be deleted when configuration is applied
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Help Text */}
      <div className="mt-4 p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Interface Configuration Examples:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>LAN Interface:</strong> Name: r1-eth0, IP: 192.168.1.1, Prefix: 24</li>
          <li>• <strong>WAN Interface:</strong> Name: r1-eth1, IP: 203.0.113.1, Prefix: 30</li>
          <li>• <strong>Point-to-Point:</strong> Name: r1-eth2, IP: 10.0.0.1, Prefix: 30</li>
          <li>• <strong>Management:</strong> Name: r1-mgmt, IP: 192.168.100.1, Prefix: 24</li>
        </ul>
      </div>
    </ConfigSection>
  );
}