#!/bin/bash
# Dynamic Emulation Container Entrypoint
# Each container serves ONE topology instance

set -e

echo "=============================================="
echo "Caduceus-Flux Dynamic Emulation Container"
echo "=============================================="
echo "Topology ID: ${TOPOLOGY_ID:-not-set}"
echo "Topology Name: ${TOPOLOGY_NAME:-not-set}"
echo "Emulation ID: ${EMULATION_ID:-not-set}"
echo "Container Hostname: $(hostname)"
echo "=============================================="

# ============================================================================
# Setup WiFi Module
# ============================================================================

echo ""
echo "📡 Setting up WiFi module..."

# Load mac80211_hwsim module for WiFi simulation
if ! lsmod | grep -q mac80211_hwsim; then
    modprobe mac80211_hwsim radios=4 2>/dev/null || echo "⚠️  WiFi module not loaded (may need host setup)"
fi

# Mount debugfs for WiFi
if ! mount | grep -q /sys/kernel/debug; then
    mount -t debugfs none /sys/kernel/debug 2>/dev/null || echo "⚠️  debugfs not mounted"
fi

# Set permissions
chmod -R 755 /sys/kernel/debug 2>/dev/null || true

echo "✅ WiFi setup complete"
echo ""
echo "Available WiFi interfaces:"
iw dev | grep Interface || echo "  (none - will be created by Mininet-WiFi)"

# ============================================================================
# Setup Open vSwitch
# ============================================================================

echo ""
echo "🔧 Starting Open vSwitch..."

# Create OVS directories
mkdir -p /var/run/openvswitch
mkdir -p /etc/openvswitch
mkdir -p /var/log/openvswitch

# Clean any stale pidfiles
rm -f /var/run/openvswitch/*.pid

# Initialize OVS database if needed
if [ ! -f /etc/openvswitch/conf.db ]; then
    echo "Creating OVS database..."
    ovsdb-tool create /etc/openvswitch/conf.db \
        /usr/share/openvswitch/vswitch.ovsschema
fi

# Start ovsdb-server
echo "Starting ovsdb-server..."
ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
    --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
    --pidfile=/var/run/openvswitch/ovsdb-server.pid \
    --detach

# Wait for ovsdb-server
sleep 1

# Initialize database
ovs-vsctl --no-wait init 2>/dev/null || true

# Start ovs-vswitchd
echo "Starting ovs-vswitchd..."
ovs-vswitchd --pidfile=/var/run/openvswitch/ovs-vswitchd.pid \
    --detach

# Wait for OVS to be ready
sleep 2

# Configure OpenFlow versions (1.0 through 1.5)
ovs-vsctl set bridge-fail-mode br0 secure 2>/dev/null || true
ovs-vsctl set-manager ptcp:6640 2>/dev/null || true

echo "✅ Open vSwitch started"

# ============================================================================
# Setup Network Namespace Support
# ============================================================================

echo ""
echo "🌐 Setting up network namespace support..."

# Make /run shared for network namespaces
mount --make-rshared /run 2>/dev/null || mount --make-shared /run 2>/dev/null || true

# Create netns directory
mkdir -p /var/run/netns

echo "✅ Network namespace support ready"

# ============================================================================
# Disable Hardware Offloading
# ============================================================================

echo ""
echo "⚙️  Disabling hardware offloading..."

for iface in $(ip link show | grep -oP '^\d+: \K[^:]+' | grep -v lo); do
    ethtool -K $iface gso off 2>/dev/null || true
    ethtool -K $iface tso off 2>/dev/null || true
    ethtool -K $iface gro off 2>/dev/null || true
done

echo "✅ Hardware offloading disabled"

# ============================================================================
# Verify Environment
# ============================================================================

echo ""
echo "🔍 Verifying environment..."
echo "Python version: $(python3 --version)"
echo "PYTHONPATH: $PYTHONPATH"

# Check Mininet-WiFi
if python3 -c "from mn_wifi.net import Mininet_wifi" 2>/dev/null; then
    echo "✅ Mininet-WiFi: Available"
else
    echo "⚠️  Mininet-WiFi: Not available"
fi

# Check Containernet
if python3 -c "from containernet.net import Containernet" 2>/dev/null; then
    echo "✅ Containernet: Available"
else
    echo "⚠️  Containernet: Not available"
fi

# Check gRPC
if python3 -c "import grpc" 2>/dev/null; then
    echo "✅ gRPC: Available"
else
    echo "⚠️  gRPC: Not available"
fi

# ============================================================================
# Start gRPC Server
# ============================================================================

echo ""
echo "=============================================="
echo "🚀 Starting gRPC Server on port ${EMULATION_SERVER_PORT}..."
echo "=============================================="
echo ""

# Execute the command passed to the container
exec "$@"
