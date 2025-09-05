import React, { useState, useEffect, useMemo } from 'react';
import {
  Play, Settings, Zap, BarChart3, AlertTriangle, CheckCircle, XCircle,
  Info, Loader, Eye, EyeOff
} from 'lucide-react';

const idOf = (h) => h?.name ?? h?.ip ?? '';

const PerformanceTests = ({
  hosts,
  testConfig,
  setTestConfig,
  onRunTest,
  loading,
  error,
  currentTest
}) => {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  // Ready hosts (iperf3 + ping), with a stable id
  const readyHosts = useMemo(
    () =>
      (Array.isArray(hosts) ? hosts : [])
        .filter((h) => h?.capabilities?.iperf3 && h?.capabilities?.ping)
        .map((h) => ({ ...h, __id: idOf(h) }))
        .filter((h) => h.__id), // drop items without an id
    [hosts]
  );

  const src = testConfig.srcHost || '';
  const dst = testConfig.dstHost || '';
  const isSamePair = src && dst && src === dst;

  // Strong pair guard: set sensible defaults and keep src/dst always different
  useEffect(() => {
    if (readyHosts.length < 2) return;

    const ids = readyHosts.map((h) => h.__id);

    // Nothing selected: choose first two distinct
    if (!src && !dst) {
      setTestConfig((prev) => ({ ...prev, srcHost: ids[0], dstHost: ids[1] }));
      return;
    }

    // If src missing or invalid, set it
    if (!ids.includes(src)) {
      const newSrc = ids[0];
      const newDst = ids.find((i) => i !== newSrc) || '';
      setTestConfig((prev) => ({ ...prev, srcHost: newSrc, dstHost: newDst }));
      return;
    }

    // If dst missing/invalid or equals src, pick a different one
    if (!ids.includes(dst) || dst === src) {
      const newDst = ids.find((i) => i !== src) || '';
      if (newDst !== dst) setTestConfig((prev) => ({ ...prev, dstHost: newDst }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readyHosts]);

  const handleSrcChange = (value) => {
    if (value === dst) {
      const alt = readyHosts.map((h) => h.__id).find((i) => i !== value) || '';
      setTestConfig((prev) => ({ ...prev, srcHost: value, dstHost: alt }));
    } else {
      setTestConfig((prev) => ({ ...prev, srcHost: value }));
    }
  };

  const handleDstChange = (value) => {
    if (value === src) {
      const alt = readyHosts.map((h) => h.__id).find((i) => i !== value) || '';
      setTestConfig((prev) => ({ ...prev, dstHost: value, srcHost: alt }));
    } else {
      setTestConfig((prev) => ({ ...prev, dstHost: value }));
    }
  };

  const swapPair = () => {
    if (!src || !dst) return;
    setTestConfig((prev) => ({ ...prev, srcHost: dst, dstHost: src }));
  };

  // Build a clean snake_case payload (used by both validate + run)
  const buildPayload = (extra = {}) => {
    const base = {
      // legacy selector for endpoint still lives in hook (`testType`),
      // but backend expects snake_case fields in the body:
      src_host: src || undefined,
      dst_host: dst || undefined,
      duration: testConfig.duration || 30,
      test_types: testConfig.testTypes || ['bandwidth', 'latency'],
      parallel_streams: testConfig.parallelStreams || 1,
      concurrent_flows: testConfig.concurrentFlows || 10,
      flow_size: testConfig.flowSize || '100M',
      ...extra
    };

    // Explicit test_type for stress/custom endpoints
    if (testConfig.testType === 'stress') {
      base.test_type = 'stress_test';
      // stress endpoint ignores src/dst; leave them, backend won't use them
    } else if (testConfig.testType === 'custom') {
      // choose a single type; default to bandwidth if none
      const single = (testConfig.testTypes && testConfig.testTypes[0]) || 'bandwidth';
      base.test_type = single;
    }

    // Also pass legacy `testType` so the hook picks the correct endpoint
    return { testType: testConfig.testType, ...base };
  };

  // ---------- Validation ----------
  const validateConfig = async () => {
    if (!src || !dst) {
      setValidationResult({ valid: false, message: 'Please select both source and destination hosts' });
      return;
    }
    if (src === dst) {
      setValidationResult({ valid: false, message: 'Source and destination hosts must be different' });
      return;
    }

    setValidating(true);
    try {
      const result = await onRunTest(buildPayload({ validate_only: true }));
      // Try to normalize various validation shapes:
      // - comprehensive: { total_tests, estimated_duration, ... }
      // - stress: { concurrent_flows, duration, flow_size, ... }
      // - some servers might wrap summaries
      const plan =
        result?.total_tests || result?.estimated_duration
          ? result
          : result?.summary || result;
      setValidationResult({ valid: true, plan });
    } catch (err) {
      setValidationResult({ valid: false, message: err?.message || 'Validation failed' });
    } finally {
      setValidating(false);
    }
  };

  // Auto-validate when pair or type changes
  useEffect(() => {
    if (src && dst && src !== dst) {
      const t = setTimeout(validateConfig, 400);
      return () => clearTimeout(t);
    } else {
      setValidationResult(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, dst, testConfig.testType]);

  // ---------- Run test ----------
  const handleRunTest = async () => {
    // Final client-side guarantee
    if (!src || !dst || src === dst) {
      setValidationResult({ valid: false, message: 'Source and destination hosts must be different' });
      return;
    }
    try {
      await onRunTest(buildPayload());
    } catch (err) {
      // surface server error
      setValidationResult({ valid: false, message: err?.message || 'Run failed' });
      // also log to console for dev
      console.error('Test failed:', err);
    }
  };

  // ---------- UI data ----------
  const testTypes = [
    { id: 'comprehensive', name: 'Comprehensive Test', description: 'Run all performance tests (bandwidth, latency, jitter, packet loss)', icon: BarChart3, color: 'blue',   estimatedDuration: (testConfig.duration || 30) * ((testConfig.testTypes?.length || 4)) },
    { id: 'stress',        name: 'Stress Test',        description: 'Test network limits with multiple concurrent flows',                                icon: Zap,      color: 'red',    estimatedDuration: (testConfig.duration || 30) },
    { id: 'custom',        name: 'Custom Test',        description: 'Run a specific test type with custom parameters',                                   icon: Settings, color: 'purple', estimatedDuration: (testConfig.duration || 30) }
  ];

  const selectedSrcHost = readyHosts.find((h) => h.__id === src);
  const selectedDstHost = readyHosts.find((h) => h.__id === dst);

  // ---------- RENDER ----------
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Performance Tests</h3>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">{readyHosts.length} hosts ready for testing</span>
          {validating && <Loader className="w-4 h-4 animate-spin text-blue-600" />}
        </div>
      </div>

      {/* Prerequisites */}
      {readyHosts.length < 2 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-yellow-600" />
            <h4 className="font-medium text-yellow-800">Prerequisites Not Met</h4>
          </div>
          <p className="text-sm text-yellow-700 mb-3">
            You need at least 2 hosts with iperf3 and ping capabilities to run performance tests.
          </p>
          <div className="text-sm text-yellow-700">
            <strong>Current status:</strong> {readyHosts.length} of {(hosts || []).length} hosts ready
          </div>
        </div>
      )}

      {/* Test Type */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {testTypes.map((type) => {
          const Icon = type.icon;
          const isSelected = testConfig.testType === type.id;
          return (
            <button
              key={type.id}
              onClick={() => {
                setTestConfig((prev) => ({
                  ...prev,
                  testType: type.id,
                  // sensible defaults per mode
                  ...(type.id === 'comprehensive'
                    ? { testTypes: prev.testTypes?.length ? prev.testTypes : ['bandwidth', 'latency', 'jitter', 'packet_loss'] }
                    : {}),
                  ...(type.id === 'custom'
                    ? { testTypes: prev.testTypes?.length ? prev.testTypes.slice(0,1) : ['bandwidth'] }
                    : {})
                }));
              }}
              className={`p-4 rounded-lg border text-left transition-all ${
                isSelected
                  ? `border-${type.color}-500 bg-${type.color}-50 ring-2 ring-${type.color}-500/20`
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
              disabled={readyHosts.length < 2}
            >
              <div className="flex items-center gap-3 mb-2">
                <Icon className={`w-6 h-6 ${isSelected ? `text-${type.color}-600` : 'text-gray-600'}`} />
                <h4 className={`font-medium ${isSelected ? `text-${type.color}-900` : 'text-gray-900'}`}>{type.name}</h4>
              </div>
              <p className="text-sm text-gray-600 mb-2">{type.description}</p>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>~{type.estimatedDuration}s</span>
                {type.id === 'comprehensive' && <span>{testConfig.testTypes?.length || 4} tests</span>}
                {type.id === 'stress' && <span>{testConfig.concurrentFlows || 10} flows</span>}
              </div>
            </button>
          );
        })}
      </div>

      {/* Host Selection */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4 items-end">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Source Host</label>
          <select
            value={src}
            onChange={(e) => handleSrcChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={readyHosts.length < 2}
          >
            <option value="">Select source host...</option>
            {readyHosts.map((h) => (
              <option key={`src-${h.__id}`} value={h.__id}>
                {h.name} ({h.ip})
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-center mb-2">
          <button
            type="button"
            onClick={swapPair}
            disabled={!src || !dst || readyHosts.length < 2}
            className="px-3 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            title="Swap source & destination"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none"><path d="M16 3l4 4-4 4M20 7H4M8 21l-4-4 4-4M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Destination Host</label>
          <select
            value={dst}
            onChange={(e) => handleDstChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={readyHosts.length < 2}
          >
            <option value="">Select destination host...</option>
            {readyHosts
              .filter((h) => h.__id !== src) // never allow same as source
              .map((h) => (
                <option key={`dst-${h.__id}`} value={h.__id}>
                  {h.name} ({h.ip})
                </option>
              ))}
          </select>
        </div>
      </div>

      {/* Inline same-pair warning */}
      {isSamePair && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
          <XCircle className="w-4 h-4 text-red-600" />
          <span className="text-sm text-red-700">Source and destination hosts must be different.</span>
        </div>
      )}

      {/* Basic Configuration */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h4 className="font-medium text-gray-900 mb-3">Test Configuration</h4>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Duration (seconds)</label>
            <input
              type="number" min="1" max="3600"
              value={testConfig.duration || 30}
              onChange={(e) =>
                setTestConfig((prev) => ({
                  ...prev,
                  duration: Math.max(1, Math.min(3600, parseInt(e.target.value) || 30))
                }))
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {testConfig.testType === 'comprehensive' && (
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Test Types</label>
              <div className="flex flex-wrap gap-2">
                {['bandwidth', 'latency', 'jitter', 'packet_loss'].map((type) => (
                  <label key={type} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={(testConfig.testTypes || []).includes(type)}
                      onChange={(e) => {
                        const types = testConfig.testTypes || [];
                        setTestConfig((prev) => ({
                          ...prev,
                          testTypes: e.target.checked ? [...types, type] : types.filter((t) => t !== type)
                        }));
                      }}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">{type.replace('_', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {testConfig.testType === 'stress' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Concurrent Flows</label>
                <input
                  type="number" min="1" max="50"
                  value={testConfig.concurrentFlows || 10}
                  onChange={(e) =>
                    setTestConfig((prev) => ({
                      ...prev,
                      concurrentFlows: Math.max(1, Math.min(50, parseInt(e.target.value) || 10))
                    }))
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Flow Size</label>
                <select
                  value={testConfig.flowSize || '100M'}
                  onChange={(e) => setTestConfig((prev) => ({ ...prev, flowSize: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="10M">10 MB</option>
                  <option value="50M">50 MB</option>
                  <option value="100M">100 MB</option>
                  <option value="500M">500 MB</option>
                  <option value="1G">1 GB</option>
                </select>
              </div>
            </>
          )}
        </div>

        {/* Advanced */}
        <div className="mt-4">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700"
          >
            {showAdvanced ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            {showAdvanced ? 'Hide' : 'Show'} Advanced Options
          </button>

          {showAdvanced && testConfig.testType === 'comprehensive' && (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Parallel Streams</label>
                <input
                  type="number" min="1" max="10"
                  value={testConfig.parallelStreams || 1}
                  onChange={(e) =>
                    setTestConfig((prev) => ({
                      ...prev,
                      parallelStreams: Math.max(1, Math.min(10, parseInt(e.target.value) || 1))
                    }))
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Validation */}
      {validationResult && (
        <div
          className={`rounded-lg p-4 ${
            validationResult.valid ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            {validationResult.valid ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600" />
            )}
            <h4 className={`font-medium ${validationResult.valid ? 'text-green-800' : 'text-red-800'}`}>
              {validationResult.valid ? 'Configuration Valid' : 'Configuration Invalid'}
            </h4>
          </div>

          {validationResult.valid ? (
            validationResult.plan && (
              <div className="text-sm text-green-700">
                <p>Test plan validated successfully:</p>
                <ul className="mt-1 list-disc list-inside">
                  <li>
                    {validationResult.plan.total_tests ??
                      validationResult.plan?.type_statistics?.stress_flow?.total ??
                      '—'}{' '}
                    total tests planned
                  </li>
                  <li>
                    Estimated duration:{' '}
                    {validationResult.plan.estimated_duration ??
                      validationResult.plan?.duration_seconds ??
                      '—'}
                    s
                  </li>
                </ul>
              </div>
            )
          ) : (
            <p className="text-sm text-red-700">{validationResult.message}</p>
          )}
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={handleRunTest}
            disabled={!validationResult?.valid || loading || readyHosts.length < 2 || isSamePair}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Running Test...
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                Run Test
              </>
            )}
          </button>

          <button
            onClick={validateConfig}
            disabled={!src || !dst || isSamePair || validating}
            className="flex items-center gap-2 px-4 py-2 text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 disabled:border-gray-300 disabled:text-gray-400 transition-colors"
          >
            {validating ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                Validating...
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4" />
                Validate
              </>
            )}
          </button>
        </div>

        {validationResult?.plan && (
          <div className="text-sm text-gray-600">
            Est. {validationResult.plan.estimated_duration ?? validationResult.plan?.duration_seconds ?? '—'}s •{' '}
            {validationResult.plan.total_tests ?? validationResult.plan?.type_statistics?.stress_flow?.total ?? '—'} tests
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <XCircle className="w-5 h-5 text-red-600" />
            <h4 className="font-medium text-red-800">Test Failed</h4>
          </div>
          <p className="text-sm text-red-700">{String(error)}</p>
        </div>
      )}

      {/* Latest Results */}
      {currentTest && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle className="w-5 h-5 text-blue-600" />
            <h4 className="font-medium text-blue-800">Latest Test Results</h4>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {currentTest.summary && (
              <>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">{currentTest.summary.successful}</div>
                  <div className="text-sm text-gray-600">Successful Tests</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-red-600">{currentTest.summary.failed}</div>
                  <div className="text-sm text-gray-600">Failed Tests</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {(currentTest.summary.duration_seconds ?? 0).toFixed
                      ? currentTest.summary.duration_seconds.toFixed(1)
                      : currentTest.summary.duration_seconds}
                    s
                  </div>
                  <div className="text-sm text-gray-600">Total Duration</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{currentTest.summary.total_tests}</div>
                  <div className="text-sm text-gray-600">Total Tests</div>
                </div>
              </>
            )}
          </div>

          {currentTest.results && currentTest.results.length > 0 && (
            <div className="mt-4">
              <h5 className="font-medium text-gray-900 mb-2">Test Details</h5>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {currentTest.results.slice(0, 3).map((result, i) => (
                  <div key={i} className="bg-white rounded p-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium capitalize">{result.test_type}</span>
                      {result.success ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500" />
                      )}
                    </div>
                    <div className="text-gray-600 mt-1">
                      {result.src_host} → {result.dst_host}
                      {typeof result.bandwidth_mbps === 'number' && (
                        <span className="ml-2 text-blue-600">{result.bandwidth_mbps.toFixed(1)} Mbps</span>
                      )}
                      {typeof result.mean_ms === 'number' && (
                        <span className="ml-2 text-purple-600">{result.mean_ms.toFixed(2)}ms avg</span>
                      )}
                      {result.error && <span className="ml-2 text-red-600">({result.error})</span>}
                    </div>
                  </div>
                ))}
                {currentTest.results.length > 3 && (
                  <div className="text-center text-sm text-gray-500">
                    +{currentTest.results.length - 3} more results
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PerformanceTests;
