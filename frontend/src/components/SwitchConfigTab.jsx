/* src/components/SwitchConfigTab.jsx */
import React, { useState, useEffect } from 'react';
import ConfigSection from './ConfigSection';
import { Network, Settings, FileText } from 'lucide-react';

const SwitchConfigTab = ({ node, onApply, loading }) => {
  const [cfg, setCfg] = useState({ version:'1.3', ip:'127.0.0.1', port:6633, fail:'secure', dpid:'' });
  const [expanded, setExpanded] = useState({ of:true, ctrl:false, flows:false });
  useEffect(()=>{ if(node){} },[node]);
  const upd=(k,v)=>setCfg(c=>({ ...c,[k]:v }));
  const tog=k=>setExpanded(e=>({ ...e,[k]:!e[k] }));
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Configure Switch: {node?.id||'—'}</h2>
        <button onClick={onApply} disabled={loading||!node} className="btn-blue">Apply</button>
      </div>
      <ConfigSection title="OpenFlow" icon={Network} expanded={expanded.of} onToggle={()=>tog('of')}>
        <select value={cfg.version} onChange={e=>upd('version',e.target.value)} className="input">
          {['1.0','1.1','1.2','1.3','1.4'].map(v=><option key={v}>{v}</option>)}
        </select>
      </ConfigSection>
      <ConfigSection title="Controller" icon={Settings} expanded={expanded.ctrl} onToggle={()=>tog('ctrl')}>
        <input value={cfg.ip} onChange={e=>upd('ip',e.target.value)} placeholder="IP" className="input" />
        <input type="number" value={cfg.port} onChange={e=>upd('port',+e.target.value)} placeholder="Port" className="input" />
        <select value={cfg.fail} onChange={e=>upd('fail',e.target.value)} className="input">
          <option value="secure">Secure</option><option value="standalone">Standalone</option>
        </select>
        <input value={cfg.dpid} onChange={e=>upd('dpid',e.target.value)} placeholder="DPID" className="input" />
      </ConfigSection>
      <ConfigSection title="Flow Tables" icon={FileText} expanded={expanded.flows} onToggle={()=>tog('flows')}>
        <p className="text-sm">Use terminal commands to view/add flows.</p>
      </ConfigSection>
    </div>
  );
};
export default SwitchConfigTab;