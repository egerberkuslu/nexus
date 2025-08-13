import React, { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { EmptyState } from '../../components/FormComponents';
import { RouterConfigHeader } from './RouterConfigHeader';
import { RouterStatusSection } from './RouterStatusSection';
import { CurrentInterfacesSection } from './CurrentInterfacesSection';
import { BasicConfigSection } from './BasicConfigSection';
import { InterfaceConfigSection } from './InterfaceConfigSection';
import { ProtocolConfigSection } from './ProtocolConfigSection';
import { StaticRoutesSection } from './StaticRoutesSection';
import { NATConfigSection } from './NATConfigSection';
import { FirewallConfigSection } from './FirewallConfigSection';
import { DryRunPlanPreview } from './DryRunPlanPreview';
import { ConfigurationSummary } from './ConfigurationSummary';
import {
  DEFAULT_PREFIX,
  normalizeInterfaces,
  normalizeRoutes,
  buildNatCommands,
  buildFirewallCommands,
  buildConfigurationSpec,
  validateConfiguration,
  initialLocal,
  reducer
} from './routerConfigUtils';

/**
 * RouterConfigTab.jsx — Enhanced with proper interface CRUD operations
 *
 * - Snapshot API: `/api/device-management/devices/:id/snapshot?detail=full`
 * - Apply-config API: `/api/device-management/apply-config`
 * - Polls snapshot every 10s while a router is selected
 * - Properly tracks interface changes for CRUD operations
 * - Supports dry-run plan preview before apply
 */

export function RouterConfigTab({
  selectedNode,
  config,
  updateConfig,
  loading = false,
  setLoading = () => { },
  showMessage = () => { },
  apiCall = () => { },
  onNetworkChange = () => { },
}) {
  const [sections, setSections] = useState({
    interfaces: true,
    protocol: false,
    staticRoutes: false,
    nat: false,
    firewall: false,
    status: true
  });
  const [snapshot, setSnapshot] = useState(null);
  const [applying, setApplying] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [planPreview, setPlanPreview] = useState([]);
  const [local, dispatch] = useReducer(reducer, initialLocal);

  // Enhanced state tracking for interfaces
  const [lastAppliedConfig, setLastAppliedConfig] = useState(null);
  const [configurationSnapshot, setConfigurationSnapshot] = useState(null);

  const pollRef = useRef(null);

  // Memoized protocol options
  const protocolOptions = useMemo(() => [
    { value: 'static', label: 'Static Routing' },
    { value: 'rip', label: 'RIP' },
    { value: 'ospf', label: 'OSPF' },
    { value: 'bgp', label: 'BGP' },
  ], []);

  const toggle = useCallback((key) => setSections((prev) => ({ ...prev, [key]: !prev[key] })), []);

  // Create a snapshot of current configuration before structural changes
  const handleInterfaceStructuralChange = useCallback(() => {
    console.log('Interface structural change - capturing current state');
    setConfigurationSnapshot({
      interfaces: JSON.parse(JSON.stringify(local.interfaces)),
      timestamp: Date.now()
    });
  }, [local.interfaces]);

  // ---------------- Snapshot polling ----------------
  const fetchSnapshot = useCallback(async () => {
    if (!selectedNode || selectedNode.type !== 'router') return;
    try {
      const res = await apiCall(`/device-management/devices/${selectedNode.id}/snapshot?detail=full`);
      if (res?.success || res?.data?.success) {
        const dev = res.device || res.data?.device || res?.data;
        setSnapshot(dev || null);
      }
    } catch (e) {
      console.warn('Router snapshot error:', e);
    }
  }, [apiCall, selectedNode?.id, selectedNode?.type]);

  useEffect(() => {
    if (selectedNode?.id && selectedNode.type === 'router') {
      fetchSnapshot();
      pollRef.current = setInterval(fetchSnapshot, 10000);
      return () => clearInterval(pollRef.current);
    }
    return undefined;
  }, [fetchSnapshot, selectedNode?.id, selectedNode?.type]);

  // ---------------- Seed UI from snapshot + external config ----------------
  useEffect(() => {
    if (!selectedNode || selectedNode.type !== 'router') return;

    const snap = snapshot || {};
    const summary = snap.summary || {};

    const snapIfs = Array.isArray(snap.interfaces) ? normalizeInterfaces(snap.interfaces, selectedNode.id) : [];
    const snapRoutes = Array.isArray(snap.routes) ? normalizeRoutes(snap.routes) : [];

    const newInterfaceConfig = config?.interfaces?.length ? config.interfaces : snapIfs.length ? snapIfs : local.interfaces;

    // Only set lastAppliedConfig when we have a fresh snapshot
    if (snap && snap.interfaces && !lastAppliedConfig) {
      setLastAppliedConfig({
        interfaces: JSON.parse(JSON.stringify(snapIfs)),
        timestamp: Date.now()
      });
    }

    dispatch({
      type: 'SET_ALL',
      payload: {
        ipForwarding: summary.ip_forwarding ?? local.ipForwarding,
        natEnabled: summary.nat_enabled ?? local.natEnabled,
        protocol: summary.routing_protocol || local.protocol,
        bgpConfig: config?.bgpConfig || local.bgpConfig,
        ospfConfig: config?.ospfConfig || local.ospfConfig,
        ripConfig: config?.ripConfig || local.ripConfig,
        interfaces: newInterfaceConfig,
        routes: config?.routes?.length ? config.routes : snapRoutes.length ? snapRoutes : local.routes,
        firewallRules: Array.isArray(config?.firewallRules)
          ? config.firewallRules
          : Array.isArray(config?.firewall?.rules)
            ? config.firewall.rules
            : local.firewallRules,
        natRules: Array.isArray(config?.natRules) ? config.natRules : local.natRules,
        legacyFirewallRules: Array.isArray(config?.legacyFirewallRules) ? config.legacyFirewallRules : local.legacyFirewallRules,
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshot, selectedNode?.id]);

  useEffect(() => {
    updateConfig?.(local);
  }, [local, updateConfig]);

  // ---------------- Configuration Validation ----------------
  const validateConfig = useCallback(() => {
    const errors = validateConfiguration(local, selectedNode);
    if (errors.length > 0) {
      showMessage(`❌ Configuration errors: ${errors.join(', ')}`, 'error');
      return false;
    }
    return true;
  }, [local, selectedNode, showMessage]);

  // ---------------- Actions ----------------
  const applyConfiguration = useCallback(async () => {
    if (!selectedNode || selectedNode.type !== 'router') return;

    // Validate configuration before applying
    if (!validateConfig()) {
      return;
    }

    setApplying(true);
    setLoading(true);

    try {
      // Use the configuration snapshot or last applied config for comparison
      const previousConfig = configurationSnapshot || lastAppliedConfig;
      const spec = buildConfigurationSpec(local, selectedNode, false, previousConfig);

      console.log('Applying configuration spec:', JSON.stringify(spec, null, 2));
      console.log('Previous config for comparison:', previousConfig);

      const res = await apiCall('/device-management/apply-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(spec),
      });

      console.log('Apply config response:', res);

      const success = res?.success ?? res?.data?.success;
      const applied = res?.applied ?? res?.data?.applied ?? 0;
      const failed = res?.failed ?? res?.data?.failed ?? 0;
      const warnings = res?.warnings ?? res?.data?.warnings ?? 0;

      if (success) {
        // Update last applied config and clear configuration snapshot
        setLastAppliedConfig({
          interfaces: JSON.parse(JSON.stringify(local.interfaces.filter(intf => intf.operation !== 'delete'))),
          protocol: local.protocol,
          timestamp: Date.now()
        });
        setConfigurationSnapshot(null);

        if (failed === 0 && warnings === 0) {
          showMessage('✅ Router configuration applied successfully', 'success');
        } else if (failed === 0 && warnings > 0) {
          showMessage(`⚠️ Configuration applied with ${warnings} warnings (check console for details)`, 'warning');
        } else {
          showMessage(`⚠️ Applied ${applied} commands, ${failed} failed, ${warnings} warnings`, 'warning');
        }

        // Clean up interfaces marked for deletion after successful apply
        const cleanedInterfaces = local.interfaces.filter(intf => intf.operation !== 'delete');
        if (cleanedInterfaces.length !== local.interfaces.length) {
          dispatch({
            type: 'SET_FIELD',
            field: 'interfaces',
            value: cleanedInterfaces
          });
        }

        setTimeout(() => {
          fetchSnapshot();
          onNetworkChange?.();
        }, 1000);
      } else if (res?.error || res?.data?.error) {
        showMessage('❌ ' + (res.error || res.data.error), 'error');
      } else {
        showMessage('❌ Failed to apply configuration', 'error');
      }
    } catch (e) {
      console.error('Apply configuration error:', e);
      showMessage('❌ ' + e.message, 'error');
    } finally {
      setApplying(false);
      setLoading(false);
    }
  }, [apiCall, validateConfig, local, selectedNode, configurationSnapshot, lastAppliedConfig, fetchSnapshot, onNetworkChange, setLoading, showMessage]);

  const previewPlan = useCallback(async () => {
    if (!selectedNode || selectedNode.type !== 'router') return;

    // Validate configuration before previewing
    if (!validateConfig()) {
      return;
    }

    setLoading(true);
    try {
      const previousConfig = configurationSnapshot || lastAppliedConfig;
      const spec = buildConfigurationSpec(local, selectedNode, true, previousConfig);

      console.log('Preview configuration spec:', JSON.stringify(spec, null, 2));
      console.log('Previous config for comparison:', previousConfig);

      const res = await apiCall('/device-management/apply-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(spec),
      });

      console.log('Preview response:', res);

      const plan = res?.plan ?? res?.data?.plan ?? [];
      setPlanPreview(Array.isArray(plan) ? plan : []);
      setDryRun(true);
      showMessage('📝 Dry‑run plan generated', 'info');
    } catch (e) {
      console.error('Preview plan error:', e);
      showMessage('❌ Failed to generate plan: ' + e.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [apiCall, validateConfig, local, selectedNode, configurationSnapshot, lastAppliedConfig, setLoading, showMessage]);

  const executeCommand = useCallback(
    async (cmd) => {
      if (!selectedNode) return { success: false };
      try {
        const response = await apiCall(`/network/hosts/${selectedNode.id}/cmd`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: cmd }),
        });
        return response?.data || response || { success: false };
      } catch (e) {
        return { success: false, error: e.message };
      }
    },
    [apiCall, selectedNode]
  );

  const testConnectivity = useCallback(
    async (target) => {
      if (!selectedNode || !target) return;
      setLoading(true);
      try {
        const r = await executeCommand(`ping -c 3 ${target}`);
        const out = r.result || r.stdout || '';
        if (/3 packets transmitted, 3 received/.test(out)) {
          showMessage(`✅ Connectivity test to ${target}: Success (0% loss)`, 'success');
        } else if (/received/.test(out)) {
          const m = out.match(/(\d+)% packet loss/);
          const loss = m ? m[1] : 'unknown';
          showMessage(`⚠️ Connectivity test to ${target}: Partial success (${loss}% loss)`, 'warning');
        } else {
          showMessage(`❌ Connectivity test to ${target}: Failed`, 'error');
        }
      } catch (e) {
        showMessage(`❌ Connectivity test failed: ${e.message}`, 'error');
      } finally {
        setLoading(false);
      }
    },
    [executeCommand, selectedNode, setLoading, showMessage]
  );

  // ---------------- Derived status from snapshot ----------------
  const status = useMemo(
    () => ({
      ipForwarding: snapshot?.summary?.ip_forwarding ?? local.ipForwarding,
      natEnabled: snapshot?.summary?.nat_enabled ?? local.natEnabled,
      interfaces: snapshot?.interfaces || [],
      routes: snapshot?.routes || [],
      nat: snapshot?.nat || {},
      firewall: snapshot?.firewall || {},
      ifstats: snapshot?.ifstats || [],
      routingProtocol: snapshot?.summary?.routing_protocol || local.protocol || 'static',
    }),
    [snapshot, local]
  );

  // ---------- helpers for rendering current NAT / Firewall succinctly ----------
  const renderNatLines = useCallback(() => {
    const lines = [];
    const m = status.nat?.masquerade || [];
    m.forEach((rule) => {
      if (rule.raw) lines.push(rule.raw);
      else lines.push(`MASQUERADE ${rule.source || ''} -> ${rule.destination || ''}`.trim());
    });
    const post = status.nat?.chains?.POSTROUTING || [];
    post.forEach((r) => lines.push(r.raw || `${r.target || ''} ${r.source || ''} ${r.option || ''} ${r.destination || ''}`.trim()));
    return lines;
  }, [status.nat]);

  const renderFirewallLines = useCallback(() => {
    const rules = status.firewall?.rules || [];
    if (!Array.isArray(rules)) return [];
    return rules.map((r, idx) => {
      if (r.rule) return r.rule;
      const chain = r.chain || 'INPUT';
      const params = r.parameters || r.params || '';
      return `${idx + 1}. ${chain} ${params}`.trim();
    });
  }, [status.firewall]);

  if (!selectedNode || selectedNode.type !== 'router') {
    return (
      <div className="p-8">
        <EmptyState
          title="No Router Selected"
          description="Please select a router from the Overview tab to configure it."
        />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      <RouterConfigHeader
        selectedNode={selectedNode}
        loading={loading}
        applying={applying}
        onPreviewPlan={previewPlan}
        onApplyConfiguration={applyConfiguration}
      />

      <RouterStatusSection
        status={status}
        sections={sections}
        loading={loading}
        onToggle={toggle}
        onRefreshStatus={fetchSnapshot}
        onTestConnectivity={testConnectivity}
      />

      <CurrentInterfacesSection status={status} />

      <BasicConfigSection local={local} dispatch={dispatch} />

      <InterfaceConfigSection
        local={local}
        selectedNode={selectedNode}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggle}
        onInterfaceStructuralChange={handleInterfaceStructuralChange}
      />

      <ProtocolConfigSection
        local={local}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggle}
        protocolOptions={protocolOptions}
        selectedNode={selectedNode}  // Required
        apiCall={apiCall}           // Required  
        showMessage={showMessage}   // Required
      />

      <StaticRoutesSection
        local={local}
        status={status}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggle}
      />

      <NATConfigSection
        local={local}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggle}
        renderNatLines={renderNatLines}
      />

      <FirewallConfigSection
        local={local}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggle}
        renderFirewallLines={renderFirewallLines}
      />

      <DryRunPlanPreview
        dryRun={dryRun}
        planPreview={planPreview}
        onHide={() => setDryRun(false)}
      />

      <ConfigurationSummary local={local} status={status} />
    </div>
  );
}

export default RouterConfigTab;