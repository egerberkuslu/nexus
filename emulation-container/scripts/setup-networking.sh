#!/bin/bash
# Caduceus-Flux Emulation Setup Script
# Prepares the system for Mininet-WiFi and network emulation

set -e

echo "Setting up Caduceus-Flux emulation environment..."

# Create necessary directories
mkdir -p /var/run/openvswitch
mkdir -p /etc/openvswitch
mkdir -p /var/log/openvswitch
mkdir -p /var/run/frr
mkdir -p /var/run/bird

# Set up network namespace support
echo "Enabling network namespace support..."
mount --make-rshared /run 2>/dev/null || true
mount --make-rshared / 2>/dev/null || true

# Load required kernel modules
echo "Loading kernel modules..."
modprobe nf_conntrack 2>/dev/null || true
modprobe nf_nat 2>/dev/null || true
modprobe sunrpc 2>/dev/null || true

# Load wireless simulation module
echo "Loading wireless simulation modules..."
modprobe mac80211_hwsim radios=0 2>/dev/null || echo "Note: mac80211_hwsim may already be loaded"

# Enable IP forwarding
echo "Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1 2>/dev/null || true
sysctl -w net.ipv6.conf.all.forwarding=1 2>/dev/null || true

# Start Open vSwitch
echo "Initializing Open vSwitch..."
if [ ! -f /etc/openvswitch/conf.db ]; then
    ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema 2>/dev/null || true
fi

# Start OVS services if not already running
if ! pgrep -x "ovsdb-server" > /dev/null 2>&1; then
    echo "Starting OVS database server..."
    ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
        --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
        --pidfile --detach /etc/openvswitch/conf.db 2>/dev/null || true
fi

if ! pgrep -x "ovs-vswitchd" > /dev/null 2>&1; then
    echo "Starting OVS daemon..."
    ovs-vswitchd --pidfile --detach --log-file=/var/log/openvswitch/ovs-vswitchd.log 2>/dev/null || true
fi

# Initialize OVS
ovs-vsctl --no-wait init 2>/dev/null || true

# Start FRR if not running
if ! pgrep -x "zebra" > /dev/null 2>&1; then
    echo "Starting FRRouting..."
    mkdir -p /var/run/frr
    chown frr:frr /var/run/frr 2>/dev/null || true

    # Setup FRR daemons file
    cat > /etc/frr/daemons <<'EOF'
zebra=yes
bgpd=yes
ospfd=yes
ospf6d=yes
ripd=yes
ripngd=yes
isisd=yes
pimd=no
ldpd=no
nhrpd=no
eigrpd=yes
babeld=no
sharpd=no
pbrd=no
bfdd=no
fabricd=no
vrrpd=no
pathd=no

vtysh_enable=yes
zebra_options="  -A 127.0.0.1 -s 90000000"
bgpd_options="   -A 127.0.0.1"
ospfd_options="  -A 127.0.0.1"
ospf6d_options=" -A ::1"
ripd_options="   -A 127.0.0.1"
ripngd_options=" -A ::1"
isisd_options="  -A 127.0.0.1"
eigrpd_options=" -A 127.0.0.1"
EOF

    /usr/lib/frr/frrinit.sh start 2>/dev/null || echo "Note: FRR startup may require additional configuration"
fi

# Configure BIRD
if ! pgrep -x "bird" > /dev/null 2>&1; then
    echo "Configuring BIRD..."
    mkdir -p /var/run/bird

    cat > /etc/bird/bird.conf <<'EOF'
log syslog all;

router id 0.0.0.1;

protocol device {
}

protocol direct {
    ipv4;
}

protocol kernel {
    ipv4 {
        export all;
    };
}

protocol static {
    ipv4;
}
EOF

    bird -c /etc/bird/bird.conf -P /var/run/bird/bird.pid 2>/dev/null || echo "Note: BIRD startup may require additional configuration"
fi

echo "Emulation environment setup complete"
exit 0
