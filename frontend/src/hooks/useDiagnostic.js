import { useState, useCallback } from 'react';

/**
 * Custom hook for network diagnostic operations
 * Integrates with your existing API pattern and logging system
 */
export const useDiagnostic = ({ apiCall, addLog }) => {
    // Diagnostic states
    const [diagnosticData, setDiagnosticData] = useState({
        networkHealth: null,
        connectivityIssues: null,
        arpTables: null,
        routingTables: null,
        switchFlows: null,
        detailedPing: null,
        historicalPings: []
    });

    const [diagnosticLoading, setDiagnosticLoading] = useState({
        health: false,
        connectivity: false,
        arp: false,
        routing: false,
        flows: false,
        ping: false,
        fixing: false,
        traceRoute: false
    });

    const [diagnosticErrors, setDiagnosticErrors] = useState({});

    // Helper function to update loading state
    const setLoadingState = useCallback((key, value) => {
        setDiagnosticLoading(prev => ({ ...prev, [key]: value }));
    }, []);

    // Helper function to handle API errors
    const handleDiagnosticError = useCallback((operation, error) => {
        const errorMessage = error.message || 'Unknown error';
        setDiagnosticErrors(prev => ({ ...prev, [operation]: errorMessage }));
        addLog(`❌ Diagnostic error (${operation}): ${errorMessage}`, 'error', 'diagnostic');
    }, [addLog]);

    // helpers at the top of the hook
    // inside useDiagnostic.js, up where you define extractJson:
    const extractJson = async resp => {
        let obj;
        // If it's a real Fetch Response, parse it
        if (resp && typeof resp.ok === 'boolean') {
            if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
            obj = await resp.json();
        } else {
            // Otherwise assume apiCall already gave parsed JSON
            obj = resp;
        }
        // If the API returns { success: true, data: {...} }, unwrap it.
        if (typeof obj === 'object' && obj !== null && obj.success === true && obj.data !== undefined) {
            return obj.data;
        }
        return obj;
    };



    const fetchNetworkHealth = useCallback(async () => {
        setLoadingState('health', true);
        setDiagnosticErrors(prev => ({ ...prev, health: null }));
        try {

            const resp = await apiCall('/diagnostic/network-health', 'GET');
            const data = await extractJson(resp);

            setDiagnosticData(prev => ({ ...prev, networkHealth: data }));
            // …log…
            return data;
        } catch (err) {
            handleDiagnosticError('health', err);
            return null;
        } finally {
            setLoadingState('health', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // diagnoseConnectivity
    const diagnoseConnectivity = useCallback(async () => {
        setLoadingState('connectivity', true);
        setDiagnosticErrors(prev => ({ ...prev, connectivity: null }));
        try {
            const resp = await apiCall('/diagnostic/connectivity', 'GET');
            const data = await extractJson(resp);

            setDiagnosticData(prev => ({ ...prev, connectivityIssues: data }));
            // …log…
            return data;
        } catch (err) {
            handleDiagnosticError('connectivity', err);
            return null;
        } finally {
            setLoadingState('connectivity', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // inside useDiagnostic…
    const fetchArpTables = useCallback(async () => {
        setLoadingState('arp', true);
        setDiagnosticErrors(prev => ({ ...prev, arp: null }));

        try {
            // apiCall now returns the JS object, not a Response
            const data = await apiCall('/diagnostic/arp-tables', 'GET');

            // stash it in state
            setDiagnosticData(prev => ({ ...prev, arpTables: data }));

            // log
            const total = Object.values(data)
                .reduce((sum, tbl) => sum + (tbl.entries?.length || 0), 0);
            addLog(
                `📋 ARP tables retrieved: ${Object.keys(data).length} hosts, ${total} total entries`,
                'info',
                'diagnostic'
            );

            return data;
        } catch (err) {
            handleDiagnosticError('arp', err);
            return null;
        } finally {
            setLoadingState('arp', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);


    // Fetch routing tables - FIXED URL
    // inside useDiagnostic…
    const fetchRoutingTables = useCallback(async () => {
        setLoadingState('routing', true);
        setDiagnosticErrors(prev => ({ ...prev, routing: null }));

        try {
            // apiCall returns parsed JSON directly
            const data = await apiCall('/diagnostic/routing-tables', 'GET');

            // stash in state
            setDiagnosticData(prev => ({ ...prev, routingTables: data }));

            // log summary
            const withGw = Object.values(data).filter(t => t.default_route).length;
            addLog(
                `🗺️ Routing tables: ${Object.keys(data).length} hosts, ${withGw} with default gateway`,
                'info',
                'diagnostic'
            );

            return data;
        } catch (err) {
            handleDiagnosticError('routing', err);
            return null;
        } finally {
            setLoadingState('routing', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // Fetch switch flow tables - FIXED URL
    // inside useDiagnostic…
    const fetchSwitchFlows = useCallback(async () => {
        setLoadingState('flows', true);
        setDiagnosticErrors(prev => ({ ...prev, flows: null }));

        try {
            // apiCall returns parsed JSON directly
            const data = await apiCall('/diagnostic/switch-flows', 'GET');

            // stash it in state
            setDiagnosticData(prev => ({ ...prev, switchFlows: data }));

            // compute totals
            const totalFlows = Object.values(data)
                .reduce((sum, sw) => sum + (sw.flow_count || 0), 0);
            const connectedCount = Object.values(data)
                .filter(sw => sw.connected).length;

            // log summary
            addLog(
                `🔄 Switch flows: ${connectedCount}/${Object.keys(data).length} switches connected, ${totalFlows} total flows`,
                'info',
                'diagnostic'
            );

            return data;
        } catch (err) {
            handleDiagnosticError('flows', err);
            return null;
        } finally {
            setLoadingState('flows', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);


    // Run detailed ping test - FIXED URL
    const runDetailedPing = useCallback(async (config = {}) => {
        const {
            source = 'h1',
            target = 'h2',
            count = 4,
            timeout = 2
        } = config;

        setLoadingState('ping', true);
        setDiagnosticErrors(prev => ({ ...prev, ping: null }));

        try {
            const response = await apiCall('/diagnostic/detailed-ping', 'POST', {
                source,
                target,
                count,
                timeout
            });

            if (response.ok) {
                const data = await response.json();
                setDiagnosticData(prev => ({
                    ...prev,
                    detailedPing: data,
                    historicalPings: [...prev.historicalPings.slice(-19), {
                        ...data,
                        timestamp: new Date().toISOString()
                    }]
                }));

                const statusIcon = data.success ? '✅' : '❌';
                const lossText = data.packet_loss === '0' ? 'perfect' : `${data.packet_loss}% loss`;
                addLog(`${statusIcon} Ping ${source}→${target}: ${lossText}, ${data.average_time_ms}ms avg`, 'info', 'diagnostic');

                return data;
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            handleDiagnosticError('ping', error);
            return null;
        } finally {
            setLoadingState('ping', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // Run trace route - FIXED URL
    const runTraceRoute = useCallback(async (source, target) => {
        setLoadingState('traceRoute', true);
        setDiagnosticErrors(prev => ({ ...prev, traceRoute: null }));

        try {
            const response = await apiCall(`/diagnostic/trace-route/${source}/${target}`, 'GET');

            if (response.ok) {
                const data = await response.json();
                addLog(`🛤️ Trace route ${source}→${target} completed`, 'info', 'diagnostic');
                return data;
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            handleDiagnosticError('traceRoute', error);
            return null;
        } finally {
            setLoadingState('traceRoute', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // Auto-fix common issues - FIXED URL
    const fixCommonIssues = useCallback(async () => {
        setLoadingState('fixing', true);
        setDiagnosticErrors(prev => ({ ...prev, fixing: null }));

        try {
            const response = await apiCall('/diagnostic/fix-common-issues', 'POST');

            if (response.ok) {
                const data = await response.json();

                if (data.success) {
                    addLog(`🔧 Auto-fix completed: ${data.fixes_applied?.length || 0} fixes applied`, 'success', 'diagnostic');

                    // Log each fix applied
                    data.fixes_applied?.forEach(fix => {
                        addLog(`  ✅ ${fix}`, 'success', 'diagnostic');
                    });

                    // Log any errors
                    data.errors?.forEach(error => {
                        addLog(`  ❌ ${error}`, 'error', 'diagnostic');
                    });

                    // Refresh diagnostic data after fixes
                    setTimeout(() => {
                        fetchNetworkHealth();
                        diagnoseConnectivity();
                    }, 2000);

                } else {
                    addLog('🔧 Auto-fix failed to complete', 'error', 'diagnostic');
                }

                return data;
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            handleDiagnosticError('fixing', error);
            return null;
        } finally {
            setLoadingState('fixing', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError, fetchNetworkHealth, diagnoseConnectivity]);

    // Comprehensive network test
    const runComprehensiveTest = useCallback(async (hosts = []) => {
        addLog('🔬 Starting comprehensive network test...', 'info', 'diagnostic');

        const results = {
            health: null,
            connectivity: null,
            pingTests: [],
            arp: null,
            routing: null,
            flows: null,
            startTime: new Date().toISOString(),
            endTime: null
        };

        try {
            // Run all diagnostic tests
            results.health = await fetchNetworkHealth();
            results.connectivity = await diagnoseConnectivity();
            results.arp = await fetchArpTables();
            results.routing = await fetchRoutingTables();
            results.flows = await fetchSwitchFlows();

            // Run ping tests between all host pairs
            if (hosts.length >= 2) {
                for (let i = 0; i < hosts.length; i++) {
                    for (let j = i + 1; j < hosts.length; j++) {
                        const pingResult = await runDetailedPing({
                            source: hosts[i],
                            target: hosts[j],
                            count: 2,
                            timeout: 1
                        });
                        if (pingResult) {
                            results.pingTests.push(pingResult);
                        }
                    }
                }
            }

            results.endTime = new Date().toISOString();

            // Summary
            const testCount = Object.values(results).filter(r => r !== null).length;
            const issues = results.health?.issues?.length || 0;
            const successfulPings = results.pingTests.filter(p => p.success).length;

            addLog(`🏁 Comprehensive test completed: ${testCount} tests, ${issues} issues, ${successfulPings}/${results.pingTests.length} pings successful`, 'info', 'diagnostic');

            return results;
        } catch (error) {
            addLog(`❌ Comprehensive test failed: ${error.message}`, 'error', 'diagnostic');
            return results;
        }
    }, [fetchNetworkHealth, diagnoseConnectivity, fetchArpTables, fetchRoutingTables, fetchSwitchFlows, runDetailedPing, addLog]);

    // Reset diagnostic data
    const resetDiagnosticData = useCallback(() => {
        setDiagnosticData({
            networkHealth: null,
            connectivityIssues: null,
            arpTables: null,
            routingTables: null,
            switchFlows: null,
            detailedPing: null,
            historicalPings: []
        });
        setDiagnosticErrors({});
        addLog('🧹 Diagnostic data cleared', 'info', 'diagnostic');
    }, [addLog]);

    // Get diagnostic summary
    const getDiagnosticSummary = useCallback(() => {
        const health = diagnosticData.networkHealth;
        const connectivity = diagnosticData.connectivityIssues;
        const lastPing = diagnosticData.detailedPing;

        return {
            overallStatus: health?.overall_status || 'unknown',
            issuesCount: (health?.issues?.length || 0) + (connectivity?.issues?.length || 0),
            suggestionsCount: (health?.recommendations?.length || 0) + (connectivity?.suggestions?.length || 0),
            lastPingSuccess: lastPing?.success || false,
            lastPingLoss: lastPing?.packet_loss || 'N/A',
            componentsHealthy: health?.components ?
                Object.values(health.components).filter(status => status === 'healthy').length : 0,
            totalComponents: health?.components ? Object.keys(health.components).length : 0,
            hasData: !!(health || connectivity || lastPing)
        };
    }, [diagnosticData]);

    return {
        // Data
        diagnosticData,
        diagnosticLoading,
        diagnosticErrors,

        // Functions
        fetchNetworkHealth,
        diagnoseConnectivity,
        fetchArpTables,
        fetchRoutingTables,
        fetchSwitchFlows,
        runDetailedPing,
        runTraceRoute,
        fixCommonIssues,
        runComprehensiveTest,
        resetDiagnosticData,
        getDiagnosticSummary,

        // Utilities
        setLoadingState,
        handleDiagnosticError
    };
};