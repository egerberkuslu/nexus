import React from 'react';
import { FiSettings } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';
import { CheckboxField } from '../../components/FormComponents';

export function BasicConfigSection({ local, dispatch }) {
  return (
    <ConfigSection title="Basic Configuration" icon={FiSettings} expanded>
      <CheckboxField 
        label="Enable IP Forwarding" 
        checked={local.ipForwarding} 
        onChange={(v) => dispatch({ type: 'SET_FIELD', field: 'ipForwarding', value: v })} 
        helper="Required for routing between networks" 
      />
    </ConfigSection>
  );
}