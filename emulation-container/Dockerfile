# Caduceus-Flux Emulation Container
# Includes: Mininet + Mininet-WiFi + Containernet + OVS + BMv2 (P4)
#
# Base image provides BMv2 binaries (e.g. simple_switch_grpc) for P4 switches.
FROM p4lang/behavioral-model:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install minimal base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    sudo \
    lsb-release \
    ca-certificates \
    gnupg \
    iproute2 \
    iptables \
    procps \
    iputils-ping && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Install Mininet from source
WORKDIR /opt
RUN apt-get update && git clone https://github.com/mininet/mininet.git && \
    cd mininet && \
    git checkout 2.3.0 && \
    PYTHON=python3 util/install.sh -nv && \
    rm -rf /var/lib/apt/lists/*

# Install wireless tools for Mininet-WiFi
RUN apt-get update && apt-get install -y --no-install-recommends \
    wireless-tools \
    wpasupplicant \
    hostapd \
    rfkill \
    iw && \
    rm -rf /var/lib/apt/lists/*

# Install Mininet-WiFi
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN pip3 install --no-cache-dir numpy==1.23.5 matplotlib==3.5.3 beautifulsoup4==4.12.3 && \
    git clone https://github.com/intrig-unicamp/mininet-wifi.git && \
    cd mininet-wifi && \
    git checkout master && \
    apt-get update && \
    PYTHON=python3 util/install.sh -Wlnfv

# Install Docker dependencies for Containernet
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

# Install Containernet (not available on PyPI; install from Git)
RUN pip3 install --no-cache-dir git+https://github.com/containernet/containernet.git

# Provide compatibility import path used by some tools/tests:
#   import containernet
#   from containernet.net import Containernet
RUN python3 - <<'PY'
import os
import site

site_packages = [p for p in site.getsitepackages() if p.endswith(("site-packages", "dist-packages"))]
target = site_packages[0] if site_packages else "/usr/local/lib/python3.11/site-packages"
pkg_dir = os.path.join(target, "containernet")
os.makedirs(pkg_dir, exist_ok=True)

with open(os.path.join(pkg_dir, "__init__.py"), "w", encoding="utf-8") as f:
    f.write("from .net import Containernet\n__all__ = ['Containernet']\n")

with open(os.path.join(pkg_dir, "net.py"), "w", encoding="utf-8") as f:
    f.write("from mininet.net import Containernet\n__all__ = ['Containernet']\n")
PY

# Install Python dependencies for gRPC agent
RUN pip3 install --no-cache-dir --ignore-installed \
    grpcio==1.59.0 \
    grpcio-tools==1.59.0 \
    protobuf==4.25.0 \
    pyyaml==6.0.1 \
    psutil==5.9.6 \
    netifaces==0.11.0 \
    docker==6.1.3 \
    requests==2.31.0 \
    urllib3==1.26.18

# Some base images ship a non-namespace `google` package that blocks `google.protobuf`.
RUN python3 - <<'PY'
import glob
import os
import sys
import site

# Remove google/__init__.py if it exists (enables PEP420 namespace package behavior).
candidate_roots = set(site.getsitepackages())
candidate_roots.update(p for p in sys.path if isinstance(p, str) and p.endswith("site-packages"))

for sp in sorted(candidate_roots):
    candidate = os.path.join(sp, "google", "__init__.py")
    try:
        if os.path.exists(candidate):
            os.remove(candidate)
    except Exception:
        pass

# Remove older protobuf eggs if present to avoid shadowing the pip-installed protobuf.
for egg in glob.glob("/usr/local/lib/python*/site-packages/protobuf-*.egg"):
    try:
        if os.path.isdir(egg):
            import shutil
            shutil.rmtree(egg)
        else:
            os.remove(egg)
    except Exception:
        pass
PY

# Copy gRPC agent code
COPY emulation-container/grpc_agent /opt/grpc_agent
COPY emulation-container/protocols /opt/protocols
COPY emulation-container/scripts /opt/scripts
COPY backend/proto /opt/proto

# Compile gRPC stubs
WORKDIR /opt/grpc_agent
RUN python3 -m grpc_tools.protoc \
    -I/opt/proto \
    --python_out=. \
    --grpc_python_out=. \
    /opt/proto/emulation.proto

# Create directories for state management
RUN mkdir -p /var/lib/caduceus-flux/{snapshots,configs,logs}

# Expose gRPC port
EXPOSE 50051

# Expose OpenFlow ports
EXPOSE 6633 6653

# Start script
COPY emulation-container/scripts/entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

WORKDIR /opt/grpc_agent

ENTRYPOINT ["/opt/entrypoint.sh"]
CMD ["python3", "server.py"]
