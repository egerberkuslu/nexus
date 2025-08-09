import { useState, useCallback } from 'react';

/**
 * Custom hook for network diagnostic operations
 * Updated to match actual API response structure
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

    // Helper to extract JSON from response
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

    // Fetch network health
    const fetchNetworkHealth = useCallback(async () => {
        setLoadingState('health', true);
        setDiagnosticErrors(prev => ({ ...prev, health: null }));
        try {
            const resp = await apiCall('/diagnostic/network-health', 'GET');
            const data = await extractJson(resp);

            setDiagnosticData(prev => ({ ...prev, networkHealth: data }));
            
            const statusIcon = data.status === 'healthy' ? '✅' : '⚠️';
            const issueCount = data.issues?.length || 0;
            addLog(`${statusIcon} Network health check: ${data.status}, ${issueCount} issues found`, 'info', 'diagnostic');
            
            return data;
        } catch (err) {
            handleDiagnosticError('health', err);
            return null;
        } finally {
            setLoadingState('health', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // Diagnose connectivity issues
    const diagnoseConnectivity = useCallback(async () => {
        setLoadingState('connectivity', true);
        setDiagnosticErrors(prev => ({ ...prev, connectivity: null }));
        try {
            const resp = await apiCall('/diagnostic/connectivity', 'GET');
            const data = await extractJson(resp);

            setDiagnosticData(prev => ({ ...prev, connectivityIssues: data }));
            
            const statusIcon = data.status === 'healthy' ? '✅' : '⚠️';
            const issueCount = data.issues?.length || 0;
            const recommendationCount = data.recommendations?.length || 0;
            
            addLog(
                `${statusIcon} Connectivity analysis: ${data.status}, ${issueCount} issues, ${recommendationCount} recommendations`, 
                issueCount > 0 ? 'warning' : 'info', 
                'diagnostic'
            );
            
            return data;
        } catch (err) {
            handleDiagnosticError('connectivity', err);
            return null;
        } finally {
            setLoadingState('connectivity', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // Fetch ARP tables
    const fetchArpTables = useCallback(async () => {
        setLoadingState('arp', true);
        setDiagnosticErrors(prev => ({ ...prev, arp: null }));

        try {
            const data = await apiCall('/diagnostic/arp-tables', 'GET');
            setDiagnosticData(prev => ({ ...prev, arpTables: data }));

            const hostCount = Object.keys(data).length;
            const totalEntries = Object.values(data)
                .reduce((sum, hostData) => sum + (hostData.arp_entries || 0), 0);
            
            addLog(
                `📋 ARP tables retrieved: ${hostCount} hosts, ${totalEntries} total entries`,
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

    // Fetch routing tables
    const fetchRoutingTables = useCallback(async () => {
        setLoadingState('routing', true);
        setDiagnosticErrors(prev => ({ ...prev, routing: null }));

        try {
            const data = await apiCall('/diagnostic/routing-tables', 'GET');
            setDiagnosticData(prev => ({ ...prev, routingTables: data }));

            const hostCount = Object.keys(data).length;
            const withDefaultRoute = Object.values(data)
                .filter(t => t.has_default_route).length;
            
            addLog(
                `🗺️ Routing tables: ${hostCount} hosts, ${withDefaultRoute} with default gateway`,
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

    // Fetch switch flow tables
    const fetchSwitchFlows = useCallback(async () => {
        setLoadingState('flows', true);
        setDiagnosticErrors(prev => ({ ...prev, flows: null }));

        try {
            const data = await apiCall('/diagnostic/switch-flows', 'GET');
            setDiagnosticData(prev => ({ ...prev, switchFlows: data }));

            const switchCount = Object.keys(data).length;
            const totalFlows = Object.values(data)
                .reduce((sum, sw) => sum + (sw.flow_count || 0), 0);
            const connectedCount = Object.values(data)
                .filter(sw => sw.connected).length;

            addLog(
                `🔄 Switch flows: ${connectedCount}/${switchCount} switches connected, ${totalFlows} total flows`,
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

    // Run detailed ping test
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

            const data = await extractJson(response);
            
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
            const avgTime = data.average_time_ms || 'N/A';
            
            addLog(
                `${statusIcon} Ping ${source}→${target}: ${lossText}, ${avgTime}ms avg`, 
                data.success ? 'info' : 'warning', 
                'diagnostic'
            );

            return data;
        } catch (error) {
            handleDiagnosticError('ping', error);
            return null;
        } finally {
            setLoadingState('ping', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // Run trace route
    const runTraceRoute = useCallback(async (source, target) => {
        setLoadingState('traceRoute', true);
        setDiagnosticErrors(prev => ({ ...prev, traceRoute: null }));

        try {
            const response = await apiCall(`/diagnostic/trace-route/${source}/${target}`, 'GET');
            const data = await extractJson(response);
            
            addLog(`🛤️ Trace route ${source}→${target} completed: ${data.hops?.length || 0} hops`, 'info', 'diagnostic');
            return data;
        } catch (error) {
            handleDiagnosticError('traceRoute', error);
            return null;
        } finally {
            setLoadingState('traceRoute', false);
        }
    }, [apiCall, addLog, setLoadingState, handleDiagnosticError]);

    // Auto-fix common issues
    const fixCommonIssues = useCallback(async () => {
        setLoadingState('fixing', true);
        setDiagnosticErrors(prev => ({ ...prev, fixing: null }));

        try {
            const response = await apiCall('/diagnostic/fix-common-issues', 'POST');
            const data = await extractJson(response);

            if (data.success) {
                const fixCount = data.fixes_applied?.length || 0;
                addLog(`🔧 Auto-fix completed: ${fixCount} fixes applied`, 'success', 'diagnostic');

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
            // Run all diagnostic tests in parallel where possible
            const [health, connectivity, arp, routing, flows] = await Promise.allSettled([
                fetchNetworkHealth(),
                diagnoseConnectivity(),
                fetchArpTables(),
                fetchRoutingTables(),
                fetchSwitchFlows()
            ]);

            results.health = health.status === 'fulfilled' ? health.value : null;
            results.connectivity = connectivity.status === 'fulfilled' ? connectivity.value : null;
            results.arp = arp.status === 'fulfilled' ? arp.value : null;
            results.routing = routing.status === 'fulfilled' ? routing.value : null;
            results.flows = flows.status === 'fulfilled' ? flows.value : null;

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
            const healthIssues = results.health?.issues?.length || 0;
            const connectivityIssues = results.connectivity?.issues?.length || 0;
            const totalIssues = healthIssues + connectivityIssues;
            const successfulPings = results.pingTests.filter(p => p.success).length;

            addLog(
                `🏁 Comprehensive test completed: ${testCount} tests, ${totalIssues} total issues, ${successfulPings}/${results.pingTests.length} pings successful`, 
                totalIssues > 0 ? 'warning' : 'success', 
                'diagnostic'
            );

            return results;
        } catch (error) {
            addLog(`❌ Comprehensive test failed: ${error.message}`, 'error', 'diagnostic');
            results.endTime = new Date().toISOString();
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

        const healthIssues = health?.issues?.length || 0;
        const connectivityIssues = connectivity?.issues?.length || 0;
        const totalIssues = healthIssues + connectivityIssues;

        const healthRecommendations = health?.recommendations?.length || 0;
        const connectivityRecommendations = connectivity?.recommendations?.length || 0;
        const totalRecommendations = healthRecommendations + connectivityRecommendations;

        return {
            overallStatus: totalIssues === 0 ? 'healthy' : 'issues_found',
            issuesCount: totalIssues,
            recommendationsCount: totalRecommendations,
            lastPingSuccess: lastPing?.success || false,
            lastPingLoss: lastPing?.packet_loss || 'N/A',
            connectivityStatus: connectivity?.status || 'unknown',
            healthStatus: health?.status || 'unknown',
            hasData: !!(health || connectivity || lastPing),
            timestamp: connectivity?.timestamp || health?.timestamp
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