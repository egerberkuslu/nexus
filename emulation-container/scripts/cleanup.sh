#!/bin/bash
# Caduceus-Flux Emulation Cleanup Script
# Cleans up resources when the emulation service stops

set +e

echo "Cleaning up Caduceus-Flux emulation environment..."

# Kill any remaining Mininet processes
echo "Stopping Mininet instances..."
pkill -f "mininet" || true
sleep 1

# Stop OVS
echo "Stopping Open vSwitch..."
pkill -f "ovs-" || true

# Clean up network namespaces
echo "Cleaning up network namespaces..."
ip -all netns delete 2>/dev/null || true

# Stop FRR services
echo "Stopping FRRouting..."
/usr/lib/frr/frrinit.sh stop 2>/dev/null || true

# Stop BIRD
echo "Stopping BIRD..."
pkill -f "bird" || true

# Remove OVS database
echo "Cleaning OVS state..."
rm -f /etc/openvswitch/conf.db.lock 2>/dev/null || true

# Clean up stale files
echo "Removing stale lock and PID files..."
rm -f /var/run/openvswitch/*.pid 2>/dev/null || true
rm -f /var/run/frr/*.pid 2>/dev/null || true
rm -f /var/run/bird/*.pid 2>/dev/null || true

echo "Cleanup complete"
exit 0
