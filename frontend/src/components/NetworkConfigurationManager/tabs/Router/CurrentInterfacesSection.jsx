import React from 'react';
import { FiWifi } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';

const DEFAULT_PREFIX = '24';

export function CurrentInterfacesSection({ status }) {
  if (!status.interfaces.length) {
    return null;
  }

  return (
    <ConfigSection title="Current Network Interfaces" icon={FiWifi} expanded>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {status.interfaces.map((intf, idx) => (
          <div key={idx} className="p-3 bg-gray-50 rounded border">
            <div className="font-medium text-gray-900">{intf.interface || intf.name}</div>
            <div className="text-sm text-gray-600">
              IP: {intf.address || (intf.ip ? `${intf.ip}/${intf.prefix || DEFAULT_PREFIX}` : 'Not configured')}
            </div>
          </div>
        ))}
      </div>
    </ConfigSection>
  );
}