import React from 'react';
import { Network, Cable, Activity, TrendingUp } from 'lucide-react';
import MetricCard from './MetricCard';

const MetricsDashboard = ({ topology, networkMetrics, packetTrend, bandwidthTrend }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
      <MetricCard
        icon={<Network className="w-6 h-6 text-blue-500" />}
        label="Active Nodes"
        value={(topology.stats.hosts || 0) + (topology.stats.switches || 0)}
        subtitle="Hosts + Switches"
        color="blue"
      />
      <MetricCard
        icon={<Cable className="w-6 h-6 text-emerald-500" />}
        label="Network Links"
        value={topology.stats.links || 0}
        subtitle="Physical connections"
        color="emerald"
      />
      <MetricCard
        icon={<Activity className="w-6 h-6 text-purple-500" />}
        label="Data Packets"
        value={networkMetrics.packets_transferred.toLocaleString()}
        trend={packetTrend}
        subtitle="Total transferred"
        color="purple"
      />
      <MetricCard
        icon={<TrendingUp className="w-6 h-6 text-orange-500" />}
        label="Bandwidth"
        value={`${networkMetrics.bandwidth_mbps.toFixed(1)} Mbps`}
        trend={bandwidthTrend}
        subtitle="Current throughput"
        color="orange"
      />
    </div>
  );
};

export default MetricsDashboard;