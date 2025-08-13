// ApplyConfigurationPanel.jsx — all-in-one, using json-edit-react with safe fallback
import React, { lazy, Suspense, useMemo, useState } from 'react'; import {
    Eye, Hammer, FileCheck2, Terminal, Check, X, AlertTriangle, Filter, Copy, ChevronDown,
    Clock, AlertCircle, Code2, Workflow
} from 'lucide-react';
/* ========================= Mini UI pieces (same-file) ========================= */
import { GUIJsonEditor } from './GUIJsonEditor'


const StatusBadge = ({ status, label }) => {
    const tone = {
        healthy: 'bg-green-100 text-green-800 border-green-200',
        warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        error: 'bg-red-100 text-red-800 border-red-200',
        info: 'bg-blue-100 text-blue-800 border-blue-200',
        neutral: 'bg-gray-100 text-gray-800 border-gray-200'
    }[status] || 'bg-gray-100 text-gray-800 border-gray-200';
    return <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${tone}`}>{label}</span>;
};

const ActionButton = ({ onClick, loading, icon, label, variant = 'primary', size = 'sm', disabled = false }) => {
    const base = 'inline-flex items-center gap-2 font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-2';
    const variantCls = variant === 'secondary'
        ? 'bg-gray-100 hover:bg-gray-200 text-gray-900 focus:ring-gray-500'
        : 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500';
    const sizeCls = size === 'sm' ? 'px-3 py-2 text-sm' : 'px-4 py-2 text-sm';
    return (
        <button
            onClick={onClick}
            disabled={disabled || loading}
            className={`${base} ${variantCls} ${sizeCls} ${(disabled || loading) ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
            {loading ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : icon}
            {label}
        </button>
    );
};

const ConfigSection = ({ title, subtitle, icon: Icon, expanded = true, actions, children }) => {
    const [isOpen, setIsOpen] = useState(expanded);
    return (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm">
            <div className="p-6 border-b border-gray-100">
                <div className="flex items-center justify-between">
                    <button onClick={() => setIsOpen(!isOpen)} className="flex items-center gap-3 group">
                        <div className="p-2 bg-gray-100 rounded-lg"><Icon size={20} className="text-gray-600" /></div>
                        <div className="text-left">
                            <h3 className="text-lg font-semibold text-black group-hover:opacity-90">{title}</h3>
                            {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
                        </div>
                    </button>
                    <div className="flex items-center gap-2">{actions}</div>
                </div>
            </div>
            {isOpen && <div className="p-6">{children}</div>}
        </div>
    );
};

const Chip = ({ label, tone = 'neutral' }) => {
    const toneCls = {
        success: 'bg-green-100 text-green-800 border-green-200',
        error: 'bg-red-100 text-red-800 border-red-200',
        warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        info: 'bg-blue-100 text-blue-800 border-blue-200',
        neutral: 'bg-gray-100 text-gray-800 border-gray-200'
    }[tone];
    return <span className={`px-2 py-1 rounded-full text-xs font-medium border ${toneCls}`}>{label}</span>;
};

const GroupCard = ({ groupKey, entries }) => {
    const [open, setOpen] = useState(true);
    const copyText = async (t) => { try { await navigator.clipboard.writeText(t); } catch (_) { } };
    const ok = entries.filter(e => e.success).length;
    const fail = entries.filter(e => !e.success && !e.ignored_error).length;
    const ign = entries.filter(e => e.ignored_error).length;

    return (
        <div className="border border-gray-200 rounded-xl overflow-hidden">
            <button className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100" onClick={() => setOpen(o => !o)}>
                <div className="flex items-center gap-3">
                    <ChevronDown size={16} className={`text-gray-600 transition-transform ${open ? 'rotate-180' : ''}`} />
                    <div>
                        <div className="font-medium text-black">{groupKey}</div>
                        <div className="text-xs text-gray-500">{entries.length} commands</div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {ok > 0 && <Chip label={`✓ ${ok}`} tone="success" />}
                    {fail > 0 && <Chip label={`✗ ${fail}`} tone="error" />}
                    {ign > 0 && <Chip label={`⚠ ${ign}`} tone="warning" />}
                </div>
            </button>

            {open && (
                <div className="divide-y divide-gray-200">
                    {entries.map((r, i) => (
                        <div key={i} className="p-4 bg-white">
                            <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                    {r.success ? <Check size={16} className="text-green-600" /> :
                                        r.ignored_error ? <AlertTriangle size={16} className="text-yellow-600" /> :
                                            <X size={16} className="text-red-600" />}
                                    <span className="text-xs uppercase tracking-wide text-gray-600 font-medium">{r.where}</span>
                                    {r.ignored_error && <Chip label="Ignored" tone="warning" />}
                                </div>
                                <button
                                    onClick={() => copyText(r.cmd)}
                                    className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-black"
                                    title="Copy command"
                                >
                                    <Copy size={12} /> Copy
                                </button>
                            </div>

                            <div className="space-y-3">
                                <div>
                                    <label className="text-xs text-gray-500">Command</label>
                                    <pre className="mt-1 p-3 bg-gray-50 border border-gray-200 rounded-md overflow-x-auto text-xs font-mono">{r.cmd}</pre>
                                </div>
                                {(r.output || r.error || r.note) && (
                                    <div>
                                        <label className="text-xs text-gray-500">Output</label>
                                        <pre className={`mt-1 p-3 border rounded-md overflow-x-auto text-xs font-mono ${r.success ? 'bg-green-50 border-green-200 text-green-800' :
                                                r.ignored_error ? 'bg-yellow-50 border-yellow-200 text-yellow-800' :
                                                    'bg-red-50 border-red-200 text-red-800'
                                            }`}>{r.output || r.error || r.note}</pre>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

/* ========================= JSON editor (json-edit-react) =========================
   We load dynamically so the app keeps working even if the package isn't ready.
   If anything fails, we fall back to a raw <textarea>.
=============================================================================== */

// Use this component where you render the GUI editor




const RawJsonTextarea = ({ value, onChange, rows = 18 }) => (
    <textarea
        className="w-full font-mono text-sm text-black bg-white rounded-lg border border-gray-300 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        spellCheck={false}
    />
);

/* ========================= Main Panel ========================= */

export const ApplyConfigurationPanel = ({ apiCall, showMessage, networkStatus }) => {
    // sensible default for your r1/h4/h6 example
    const defaultConfig = {
        routers: {
            r1: {
                sysctl: { "net.ipv4.ip_forward": "1" },
                interfaces: [
                    { name: "r1-eth0", flush: true, addresses: ["10.0.1.1/24"], state: "up" },
                    { name: "r1-eth1", flush: true, addresses: ["10.0.2.1/24"], state: "up" }
                ]
            }
        },
        hosts: {
            h4: {
                interfaces: [{ name: "h4-eth0", flush: true, addresses: ["10.0.1.10/24"], state: "up" }],
                routes: [
                    { action: "del", destination: "default", ignore_error: true },
                    { action: "add", destination: "default", via: "10.0.1.1" }
                ]
            },
            h6: {
                interfaces: [{ name: "h6-eth0", flush: true, addresses: ["10.0.2.10/24"], state: "up" }],
                routes: [
                    { action: "del", destination: "default", ignore_error: true },
                    { action: "add", destination: "default", via: "10.0.2.1" }
                ]
            }
        }
    };

    const [configJson, setConfigJson] = useState(JSON.stringify(defaultConfig, null, 2));
    const [useRawMode, setUseRawMode] = useState(false); // quick toggle between GUI and raw
    const parseSpec = useMemo(() => { try { return JSON.parse(configJson); } catch { return null; } }, [configJson]);

    const [previewPlan, setPreviewPlan] = useState(null);
    const [applyResult, setApplyResult] = useState(null);
    const [applyLoading, setApplyLoading] = useState(false);
    const [filterStatus, setFilterStatus] = useState('all'); // all | success | failed | ignored
    const [filterText, setFilterText] = useState('');

    // ---- API calls
    const onPreviewConfig = async () => {
        if (!parseSpec) return showMessage('Invalid JSON. Please fix the configuration.', 'error');
        setApplyLoading(true);
        setPreviewPlan(null);
        setApplyResult(null);
        try {
            const res = await apiCall('/device-management/apply-config', {
                method: 'POST',
                body: JSON.stringify({ ...parseSpec, validate_only: true })
            });
            const plan = res?.data?.plan || res?.plan || [];
            setPreviewPlan(plan);
            showMessage(`Preview generated with ${plan.length} command(s).`, 'success');
        } catch (e) {
            showMessage(e?.message || 'Preview failed', 'error');
        } finally {
            setApplyLoading(false);
        }
    };

    const onApplyConfig = async () => {
        if (!parseSpec) return showMessage('Invalid JSON. Please fix the configuration.', 'error');
        setApplyLoading(true);
        setApplyResult(null);
        try {
            const res = await apiCall('/device-management/apply-config', {
                method: 'POST',
                body: JSON.stringify({ ...parseSpec, validate_only: false })
            });
            const data = res?.data || res; // supports both wrapped/unwrapped
            setApplyResult(data);
            const ok = (data?.failed || 0) === 0;
            const applied = data?.applied ?? 0;
            const failed = data?.failed ?? 0;
            showMessage(ok ? `Applied ${applied} command(s) successfully.` : `Applied with errors: ${applied} ok, ${failed} failed.`, ok ? 'success' : 'warning');
        } catch (e) {
            showMessage(e?.message || 'Apply failed', 'error');
        } finally {
            setApplyLoading(false);
        }
    };

    // ---- Group + filter results
    const groupedResults = useMemo(() => {
        const results = applyResult?.results || [];
        return results.reduce((acc, r) => {
            const key = `${r.node} • ${r.where}`;
            (acc[key] = acc[key] || []).push(r);
            return acc;
        }, {});
    }, [applyResult]);

    const filteredGroups = useMemo(() => {
        const filterOne = (r) => {
            if (filterStatus === 'success' && !r.success) return false;
            if (filterStatus === 'failed' && r.success) return false;
            if (filterStatus === 'ignored' && !r.ignored_error) return false;
            if (filterText) {
                const q = filterText.toLowerCase();
                const hay = `${r.node} ${r.where} ${r.cmd} ${r.output || ''} ${r.error || ''}`.toLowerCase();
                if (!hay.includes(q)) return false;
            }
            return true;
        };
        return Object.entries(groupedResults)
            .map(([k, arr]) => [k, arr.filter(filterOne)])
            .filter(([, arr]) => arr.length > 0);
    }, [groupedResults, filterStatus, filterText]);

    return (
        <ConfigSection
            title="Apply Configuration"
            subtitle="Create & apply JSON-based configuration to routers, hosts, switches, and controllers"
            icon={Hammer}
            expanded
            actions={
                <div className="flex items-center gap-2">
                    <ActionButton
                        onClick={onPreviewConfig}
                        loading={applyLoading}
                        icon={<Eye size={16} />}
                        label="Preview"
                        variant="secondary"
                    />
                    <ActionButton
                        onClick={onApplyConfig}
                        loading={applyLoading}
                        icon={<FileCheck2 size={16} />}
                        label="Apply"
                        variant="secondary"
                        disabled={!networkStatus?.running}
                    />
                </div>
            }
        >
            <div className="space-y-6">
                {/* JSON Editor (GUI or Raw) */}
                <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
                    <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-semibold text-black">Configuration</h4>
                        <div className="flex items-center gap-2">
                            {parseSpec ? <StatusBadge status="healthy" label="Valid JSON" /> : <StatusBadge status="error" label="Invalid JSON" />}
                            <button
                                onClick={() => setUseRawMode(!useRawMode)}
                                className="inline-flex items-center gap-1 text-xs px-2 py-1 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                                title="Toggle between GUI/Raw editor"
                            >
                                {useRawMode ? <span className="font-medium">GUI</span> : <span className="font-medium">Raw</span>}
                            </button>
                        </div>
                    </div>

                    {useRawMode ? (
                        <RawJsonTextarea value={configJson} onChange={setConfigJson} rows={24} />
                    ) : (
                        <GUIJsonEditor value={configJson} onChange={setConfigJson} headerHeight={112} />
                    )}

                    <div className="mt-3 text-xs text-gray-600">
                        <p className="mb-1"><strong>Tips:</strong></p>
                        <ul className="space-y-1 ml-4">
                            <li>• Use <code className="bg-gray-200 px-1 rounded">"flush": true</code> to clear addresses before adding new ones</li>
                            <li>• Add <code className="bg-gray-200 px-1 rounded">"ignore_error": true</code> for routes that might not exist</li>
                            <li>• Click <strong>Preview</strong> to see the exact commands before applying</li>
                        </ul>
                    </div>
                </div>

                {/* Preview */}
                <div className="bg-white rounded-xl border border-gray-200">
                    <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 rounded-t-xl">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Terminal size={16} className="text-gray-600" />
                                <h4 className="text-sm font-semibold text-black">Execution Preview</h4>
                            </div>
                            <StatusBadge status={previewPlan ? 'info' : 'neutral'} label={previewPlan ? `${previewPlan.length} command(s)` : 'No preview'} />
                        </div>
                    </div>
                    <div className="p-4">
                        {previewPlan ? (
                            <div className="space-y-3 max-h-64 overflow-auto">
                                {previewPlan.map((item, idx) => (
                                    <div key={idx} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="flex items-center gap-2">
                                                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                                    {item.node}
                                                </span>
                                                <span className="text-xs text-gray-500">•</span>
                                                <span className="text-xs uppercase text-gray-600 font-medium">{item.where}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-gray-500">#{idx + 1}</span>
                                                {item.ignore_error && (
                                                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                                        Ignore Errors
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <pre className="bg-white border border-gray-200 rounded-md p-3 text-xs font-mono overflow-x-auto">{item.cmd}</pre>
                                    </div>
                                ))}

                                {/* Preview Summary */}
                                <div className="mt-4 pt-3 border-t border-gray-200">
                                    <div className="grid grid-cols-3 gap-4 text-center">
                                        <div>
                                            <p className="text-xs text-gray-500">Total Commands</p>
                                            <p className="font-bold text-black">{previewPlan.length}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-gray-500">Will Ignore Errors</p>
                                            <p className="font-bold text-yellow-600">
                                                {previewPlan.filter(i => i.ignore_error).length}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-gray-500">Affected Nodes</p>
                                            <p className="font-bold text-blue-600">
                                                {new Set(previewPlan.map(i => i.node)).size}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="text-center py-8">
                                <Terminal className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                                <p className="text-gray-500">Click Preview to see execution plan</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Results */}
                <div className="bg-white rounded-xl border border-gray-200">
                    <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 rounded-t-xl">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Terminal size={16} className="text-gray-600" />
                                <h4 className="text-sm font-semibold text-black">Execution Results</h4>
                            </div>
                            <div className="flex items-center gap-2">
                                {applyResult && (
                                    <>
                                        <StatusBadge
                                            status={applyResult.failed === 0 ? 'healthy' : 'warning'}
                                            label={`Applied: ${applyResult.applied || 0}`}
                                        />
                                        {applyResult.failed > 0 && (
                                            <StatusBadge status="error" label={`Failed: ${applyResult.failed}`} />
                                        )}
                                        {applyResult.timestamp && (
                                            <StatusBadge status="info" label={new Date(applyResult.timestamp).toLocaleTimeString()} />
                                        )}
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="p-4">
                        {applyResult ? (
                            <div className="space-y-4">
                                {/* Summary Cards */}
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                                        <div className="flex items-center gap-2">
                                            <Check className="w-5 h-5 text-green-600" />
                                            <span className="text-sm font-medium text-green-800">Successful</span>
                                        </div>
                                        <p className="text-2xl font-bold text-green-900 mt-1">{applyResult.applied || 0}</p>
                                    </div>

                                    <div className={`rounded-lg p-4 border ${applyResult.failed ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'}`}>
                                        <div className="flex items-center gap-2">
                                            <X className={`w-5 h-5 ${applyResult.failed ? 'text-red-600' : 'text-gray-500'}`} />
                                            <span className={`text-sm font-medium ${applyResult.failed ? 'text-red-800' : 'text-gray-700'}`}>
                                                Failed
                                            </span>
                                        </div>
                                        <p className={`text-2xl font-bold mt-1 ${applyResult.failed ? 'text-red-900' : 'text-gray-800'}`}>{applyResult.failed || 0}</p>
                                    </div>

                                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                        <div className="flex items-center gap-2">
                                            <Clock className="w-5 h-5 text-blue-600" />
                                            <span className="text-sm font-medium text-blue-800">Total</span>
                                        </div>
                                        <p className="text-2xl font-bold text-blue-900 mt-1">{applyResult.results?.length || 0}</p>
                                    </div>
                                </div>

                                {/* Filters */}
                                <div className="flex flex-col md:flex-row gap-3 p-3 bg-gray-50 rounded-lg">
                                    <div className="flex items-center gap-2">
                                        <Filter size={16} className="text-gray-600" />
                                        <select
                                            value={filterStatus}
                                            onChange={(e) => setFilterStatus(e.target.value)}
                                            className="border border-gray-300 rounded-md px-3 py-1 text-sm bg-white"
                                        >
                                            <option value="all">All Results</option>
                                            <option value="success">Success Only</option>
                                            <option value="failed">Failed Only</option>
                                            <option value="ignored">Ignored Errors</option>
                                        </select>
                                    </div>
                                    <input
                                        placeholder="Search in commands, nodes, or output..."
                                        value={filterText}
                                        onChange={(e) => setFilterText(e.target.value)}
                                        className="flex-1 border border-gray-300 rounded-md px-3 py-1 text-sm"
                                    />
                                </div>

                                {/* Grouped details */}
                                <div className="space-y-3 max-h-96 overflow-auto">
                                    {applyResult.results && applyResult.results.length > 0 ? (
                                        (() => {
                                            if (filteredGroups.length === 0) {
                                                return (
                                                    <div className="text-center py-8">
                                                        <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                                                        <p className="text-gray-500">No results match the current filters</p>
                                                        <p className="text-xs text-gray-400 mt-2">
                                                            Total results: {applyResult.results.length}
                                                        </p>
                                                        <p className="text-xs text-gray-400">
                                                            Filter: {filterStatus}, Search: “{filterText}”
                                                        </p>
                                                    </div>
                                                );
                                            }
                                            return filteredGroups.map(([groupKey, entries], gi) => (
                                                <GroupCard key={gi} groupKey={groupKey} entries={entries} />
                                            ));
                                        })()
                                    ) : (
                                        <div className="text-center py-8">
                                            <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                                            <p className="text-gray-500">No detailed results available</p>
                                            <p className="text-xs text-gray-400 mt-2">
                                                The configuration was applied but no command details were returned
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div className="text-center py-8">
                                <FileCheck2 className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                                <p className="text-gray-500">Click Apply to execute configuration</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </ConfigSection>
    );
};

export default ApplyConfigurationPanel;

