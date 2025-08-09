/* src/components/ControllerConfigTab.jsx */
import React from 'react';
import ConfigSection from './ConfigSection';
import { Settings, Code, Activity, Play, Square, RotateCcw } from 'lucide-react';

const ControllerConfigTab = ({ node, controllerStatus, onStart, onStop, loading }) => (
  <div className="space-y-6">
    <div className="flex justify-between items-center">
      <h2 className="text-xl font-semibold">Controller: {node?.id||'—'}</h2>
    </div>
    <ConfigSection title="Management" icon={Activity} expanded actions={
      controllerStatus.running ? (
        <>
          <button onClick={onStop} disabled={loading} className="btn-red"><Square/> Stop</button>
          <button onClick={onStart} disabled={loading} className="btn-yellow"><RotateCcw/> Restart</button>
        </>
      ) : (
        <button onClick={onStart} disabled={loading} className="btn-green"><Play/> Start</button>
      )
    }>
      <div>Status: {controllerStatus.running?'Running':'Stopped'}</div>
    </ConfigSection>
  </div>
);
export default ControllerConfigTab;