#!/bin/bash
# Caduceus-Flux Emulation Container Entrypoint

set -e

echo "Starting Caduceus-Flux Emulation Container..."

# Start Open vSwitch
echo "Starting Open vSwitch..."
mkdir -p /var/run/openvswitch
mkdir -p /etc/openvswitch
mkdir -p /var/log/openvswitch

# Create OVS database if it doesn't exist
if [ ! -f /etc/openvswitch/conf.db ]; then
    echo "Creating OVS database..."
    ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
fi

ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
    --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
    --pidfile --detach /etc/openvswitch/conf.db

ovs-vsctl --no-wait init || true

ovs-vswitchd --pidfile --detach --log-file=/var/log/openvswitch/ovs-vswitchd.log

# Enable all OpenFlow versions
ovs-vsctl set bridge br0 protocols=OpenFlow10,OpenFlow11,OpenFlow12,OpenFlow13,OpenFlow14,OpenFlow15 2>/dev/null || true

echo "Open vSwitch started"

# Start FRRouting daemons
echo "Starting FRRouting..."
mkdir -p /var/run/frr
mkdir -p /etc/frr
chown frr:frr /var/run/frr 2>/dev/null || echo "FRR user not available, skipping chown"

# Enable all routing protocols in daemons file
cat > /etc/frr/daemons <<EOF
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

# Start FRR services if available
if [ -f /usr/lib/frr/frrinit.sh ]; then
    /usr/lib/frr/frrinit.sh start || echo "FRR services starting..."
    echo "FRRouting started"
else
    echo "FRR not installed, skipping..."
fi

# Configure BIRD if available
if [ -d /etc/bird ]; then
    echo "Configuring BIRD..."
    mkdir -p /var/run/bird
    cat > /etc/bird/bird.conf <<EOF
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
    echo "BIRD configured"
else
    echo "BIRD not installed, skipping..."
fi

# Load kernel modules for wireless
echo "Loading wireless kernel modules..."
modprobe mac80211_hwsim radios=0 2>/dev/null || echo "mac80211_hwsim already loaded or not available"

# Optional realistic wireless channel (wmediumd). Only reported when requested;
# the emulation agent falls back to the ideal channel if anything is missing.
case "${CADUCEUS_WMEDIUMD:-}" in
    1|true|TRUE|True|yes|YES|on|ON|enable|enabled)
        if command -v wmediumd >/dev/null 2>&1; then
            echo "wmediumd requested and available at $(command -v wmediumd)"
            echo "  noise_th=${CADUCEUS_NOISE_TH:--91}, logDistance exp=${CADUCEUS_PROP_EXP:-4.0}"
        else
            echo "WARNING: CADUCEUS_WMEDIUMD is set but the wmediumd binary is missing;"
            echo "         the emulation will fall back to the ideal wireless channel."
        fi
        ;;
esac

# Disable hardware offloading for better compatibility
ethtool -K eth0 tx off rx off 2>/dev/null || true

# Set up network namespace support (only if /run is a mountpoint)
if mountpoint -q /run; then
    mount --make-rshared /run || true
else
    echo "/run is not a mountpoint; skipping rshared remount"
fi

echo "Emulation environment ready"

# Execute the command
exec "$@"
