# Mininet Web Framework Architecture

## System Overview

The Mininet Web Framework is a comprehensive multi-tier architecture designed to provide web-based management of software-defined networks with AI-powered automation. The system consists of four main components that work together to deliver a complete network simulation and management solution.

```mermaid
graph TB
    subgraph "User Interface Layer"
        UI[Web UI - React Frontend]
        AI[AI Assistants]
        CLI[CLI Tools]
    end
    
    subgraph "API Gateway Layer"
        MCP[MCP Server<br/>Model Context Protocol]
        REST[REST API<br/>Flask Backend]
    end
    
    subgraph "Core Logic Layer"
        NM[Network Manager]
        TM[Topology Manager]
        CM[Controller Manager]
        PM[Performance Manager]
        DM[Diagnostic Manager]
        LLM[LLM Service]
    end
    
    subgraph "Network Infrastructure Layer"
        MIN[Mininet Engine]
        OVS[Open vSwitch]
        CTRL[SDN Controllers]
    end
    
    subgraph "Data Layer"
        MONGO[(MongoDB)]
        SNAP[Snapshots]
        CONF[Configurations]
    end
    
    UI --> REST
    AI --> MCP
    CLI --> REST
    MCP --> REST
    REST --> NM
    REST --> TM
    REST --> CM
    REST --> PM
    REST --> DM
    REST --> LLM
    NM --> MIN
    CM --> CTRL
    TM --> OVS
    PM --> MIN
    DM --> MIN
    REST --> MONGO
    SNAP --> MONGO
    CONF --> MONGO
```

## Component Architecture

### Frontend Architecture

The React frontend follows a modern component-based architecture with hooks and functional components.

```mermaid
graph TD
    subgraph "React Frontend Architecture"
        APP[App.jsx<br/>Main Container]
        
        subgraph "Core Components"
            NETVIS[Network Visualization]
            NETCONFIG[Network Configuration]
            PERFMON[Performance Monitor]
            DIAG[Diagnostics Panel]
        end
        
        subgraph "Manager Components"
            LLMGR[LLM Manager]
            SNAPMGR[Snapshot Manager]
            STOREMGR[Storage Manager]
            CONFIGMGR[Config Manager]
        end
        
        subgraph "Custom Hooks"
            APIHOOK[useApiCall]
            NETHOOK[useNetworkData]
            CTRLHOOK[useControllerData]
            DIAGHOOK[useDiagnostic]
        end
        
        subgraph "Utility Layer"
            UTILS[Formatters & Helpers]
            ICONS[Icon Libraries]
            STYLES[Tailwind CSS]
        end
    end
    
    APP --> NETVIS
    APP --> NETCONFIG
    APP --> PERFMON
    APP --> DIAG
    APP --> LLMGR
    APP --> SNAPMGR
    APP --> STOREMGR
    APP --> CONFIGMGR
    
    NETVIS --> APIHOOK
    NETCONFIG --> NETHOOK
    PERFMON --> NETHOOK
    DIAG --> DIAGHOOK
    LLMGR --> APIHOOK
    
    APIHOOK --> UTILS
    NETHOOK --> UTILS
    CTRLHOOK --> UTILS
    DIAGHOOK --> UTILS
```

### Backend Architecture

The Flask backend implements a modular blueprint-based architecture with clear separation of concerns.

```mermaid
graph TB
    subgraph "Flask Backend Architecture"
        MAIN[app.py<br/>Main Application]
        
        subgraph "API Blueprints"
            NETAPI[network_routes.py]
            CTRLAPI[controller_routes.py]
            TOPOAPI[topology_routes.py]
            STATSAPI[stats_routes.py]
            SNAPAPI[snapshot_routes.py]
            LLMAPI[llm_routes.py]
            DIAGAPI[diagnostic_routes.py]
            HOSTAPI[host_management.py]
            PERFAPI[performance_management.py]
        end
        
        subgraph "Core Managers"
            MINMGR[MininetManager]
            NETMGR[NetworkManager]
            TOPOMGR[TopologyManager]
            CTRLMGR[ControllerManager]
            PERFMGR[PerformanceManager]
        end
        
        subgraph "Specialized Components"
            LLMSVC[LLM Service]
            DIAGSVC[Diagnostic Service]
            STATSVC[Stats Collector]
            SNAPMGR[Snapshot Manager]
        end
        
        subgraph "Utilities & Infrastructure"
            LOGGER[Logger]
            CONFIG[Config Manager]
            CRYPTO[Encryption Utils]
            DB[Database Layer]
        end
    end
    
    MAIN --> NETAPI
    MAIN --> CTRLAPI
    MAIN --> TOPOAPI
    MAIN --> STATSAPI
    MAIN --> SNAPAPI
    MAIN --> LLMAPI
    MAIN --> DIAGAPI
    MAIN --> HOSTAPI
    MAIN --> PERFAPI
    
    NETAPI --> MINMGR
    CTRLAPI --> CTRLMGR
    TOPOAPI --> TOPOMGR
    PERFAPI --> PERFMGR
    LLMAPI --> LLMSVC
    DIAGAPI --> DIAGSVC
    STATSAPI --> STATSVC
    SNAPAPI --> SNAPMGR
    
    MINMGR --> LOGGER
    NETMGR --> CONFIG
    CTRLMGR --> CRYPTO
    ALL --> DB
```

### MCP Server Architecture

The MCP server provides a standardized protocol interface for AI assistant integration.

```mermaid
graph LR
    subgraph "MCP Server Architecture"
        subgraph "Protocol Layer"
            STDIO[STDIO Transport]
            HTTP[HTTP Transport]
            JSONRPC[JSON-RPC Handler]
        end
        
        subgraph "Server Implementations"
            FASTMCP[FastMCP Server]
            STDMCP[Standard MCP Server]
            BRIDGE[Node.js Bridge]
        end
        
        subgraph "Tool Management"
            TOOLREG[Tool Registry]
            TOOLHAND[Tool Handler]
            TOOLDEF[Tool Definitions]
        end
        
        subgraph "Resource Management"
            RESREG[Resource Registry]
            RESHAND[Resource Handler]
            RESPROV[Resource Providers]
        end
        
        subgraph "Backend Integration"
            HTTPCLIENT[HTTP Client]
            APICALLS[API Calls]
            ERRHAND[Error Handler]
        end
    end
    
    STDIO --> FASTMCP
    HTTP --> BRIDGE
    JSONRPC --> STDMCP
    
    FASTMCP --> TOOLREG
    STDMCP --> TOOLREG
    BRIDGE --> TOOLREG
    
    TOOLREG --> TOOLHAND
    TOOLHAND --> TOOLDEF
    
    TOOLREG --> RESREG
    RESREG --> RESHAND
    RESHAND --> RESPROV
    
    TOOLHAND --> HTTPCLIENT
    HTTPCLIENT --> APICALLS
    APICALLS --> ERRHAND
```

## Data Flow Architecture

### Request Flow Diagram

```mermaid
sequenceDiagram
    participant UI as Frontend UI
    participant API as Flask API
    participant MGR as Core Managers
    participant MIN as Mininet
    participant DB as Database
    
    UI->>API: HTTP Request
    API->>MGR: Business Logic Call
    MGR->>MIN: Network Operation
    MIN-->>MGR: Result
    MGR->>DB: Persist Data
    DB-->>MGR: Confirmation
    MGR-->>API: Response Data
    API-->>UI: JSON Response
    
    Note over UI: Update React State
    Note over API: Log Operation
    Note over DB: Store Snapshot
```

### MCP Tool Execution Flow

```mermaid
sequenceDiagram
    participant AI as AI Assistant
    participant MCP as MCP Server
    participant API as Flask API
    participant MIN as Mininet
    
    AI->>MCP: Tool Call Request
    MCP->>MCP: Validate Parameters
    MCP->>API: HTTP API Call
    API->>MIN: Network Operation
    MIN-->>API: Operation Result
    API-->>MCP: JSON Response
    MCP->>MCP: Process Response
    MCP-->>AI: Tool Result
    
    Note over AI: Natural Language Processing
    Note over MCP: Protocol Compliance
    Note over API: Business Logic
    Note over MIN: Network Execution
```

### Real-time Data Flow

```mermaid
graph LR
    subgraph "Data Collection"
        STATS[Stats Collector]
        PERF[Performance Monitor]
        DIAG[Diagnostic Engine]
    end
    
    subgraph "Data Processing"
        AGG[Aggregator]
        FILTER[Filter Engine]
        TRANSFORM[Transformer]
    end
    
    subgraph "Storage Layer"
        MEMORY[In-Memory Cache]
        PERSIST[Persistent Storage]
        HISTORY[Historical Data]
    end
    
    subgraph "Delivery Layer"
        REST[REST Endpoints]
        WS[WebSocket Streams]
        MCP[MCP Resources]
    end
    
    STATS --> AGG
    PERF --> AGG
    DIAG --> AGG
    
    AGG --> FILTER
    FILTER --> TRANSFORM
    
    TRANSFORM --> MEMORY
    TRANSFORM --> PERSIST
    PERSIST --> HISTORY
    
    MEMORY --> REST
    MEMORY --> WS
    HISTORY --> MCP
```

## Network Architecture

### SDN Architecture Integration

```mermaid
graph TB
    subgraph "Application Layer"
        WEBAPP[Web Application]
        AI[AI Assistant]
        MONITORING[Monitoring Tools]
    end
    
    subgraph "Control Layer"
        subgraph "SDN Controllers"
            RYU[Ryu Controller]
            POX[POX Controller]
            ODL[OpenDaylight]
        end
        
        subgraph "Management Services"
            FLOWMGR[Flow Manager]
            TOPOMGR[Topology Manager]
            NETMGR[Network Manager]
        end
    end
    
    subgraph "Infrastructure Layer"
        subgraph "Virtual Switches"
            OVS1[OVS Switch 1]
            OVS2[OVS Switch 2]
            OVS3[OVS Switch N]
        end
        
        subgraph "Virtual Hosts"
            HOST1[Host 1]
            HOST2[Host 2]
            HOST3[Host N]
        end
    end
    
    subgraph "Physical Layer"
        MININET[Mininet Engine]
        KERNEL[Linux Kernel]
        NETNS[Network Namespaces]
    end
    
    WEBAPP --> FLOWMGR
    AI --> TOPOMGR
    MONITORING --> NETMGR
    
    FLOWMGR --> RYU
    TOPOMGR --> POX
    NETMGR --> ODL
    
    RYU --> OVS1
    POX --> OVS2
    ODL --> OVS3
    
    OVS1 --> HOST1
    OVS2 --> HOST2
    OVS3 --> HOST3
    
    OVS1 --> MININET
    OVS2 --> MININET
    OVS3 --> MININET
    HOST1 --> MININET
    HOST2 --> MININET
    HOST3 --> MININET
    
    MININET --> KERNEL
    KERNEL --> NETNS
```

### Network Topology Models

```mermaid
graph TD
    subgraph "Topology Abstractions"
        subgraph "Linear Topology"
            L1[Host 1] --- L2[Switch 1] --- L3[Host 2] --- L4[Switch 2] --- L5[Host 3]
        end
        
        subgraph "Tree Topology"
            T1[Root Switch]
            T1 --- T2[Switch 1]
            T1 --- T3[Switch 2]
            T2 --- T4[Host 1]
            T2 --- T5[Host 2]
            T3 --- T6[Host 3]
            T3 --- T7[Host 4]
        end
        
        subgraph "Custom Topology"
            C1[Host A] --- C2[Switch A] --- C3[Switch B] --- C4[Host B]
            C2 --- C5[Switch C] --- C6[Host C]
            C3 --- C7[Controller]
            C5 --- C8[Host D]
        end
    end
```

## Design Patterns

### Singleton Pattern (Network Manager)

```python
class MininetManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.net = None
            self.is_running = False
            self._initialized = True
```

### Factory Pattern (Controller Factory)

```python
class ControllerFactory:
    @staticmethod
    def create_controller(controller_type, **kwargs):
        if controller_type == 'ryu':
            return RyuController(**kwargs)
        elif controller_type == 'pox':
            return POXController(**kwargs)
        elif controller_type == 'opendaylight':
            return OpenDaylightController(**kwargs)
        else:
            raise ValueError(f"Unknown controller type: {controller_type}")
```

### Observer Pattern (Event System)

```python
class EventManager:
    def __init__(self):
        self.listeners = defaultdict(list)
    
    def subscribe(self, event_type, callback):
        self.listeners[event_type].append(callback)
    
    def emit(self, event_type, data):
        for callback in self.listeners[event_type]:
            callback(data)
```

### Builder Pattern (Topology Builder)

```python
class TopologyBuilder:
    def __init__(self):
        self.hosts = []
        self.switches = []
        self.links = []
        self.controllers = []
    
    def add_host(self, name, ip=None, mac=None):
        self.hosts.append({'name': name, 'ip': ip, 'mac': mac})
        return self
    
    def add_switch(self, name, dpid=None):
        self.switches.append({'name': name, 'dpid': dpid})
        return self
    
    def build(self):
        return {
            'hosts': self.hosts,
            'switches': self.switches,
            'links': self.links,
            'controllers': self.controllers
        }
```

## Performance Architecture

### Scaling Strategies

```mermaid
graph TB
    subgraph "Horizontal Scaling"
        LB[Load Balancer]
        API1[API Instance 1]
        API2[API Instance 2]
        API3[API Instance N]
        
        LB --> API1
        LB --> API2
        LB --> API3
    end
    
    subgraph "Vertical Scaling"
        CACHE[Redis Cache]
        QUEUE[Message Queue]
        WORKER[Background Workers]
        
        API1 --> CACHE
        API2 --> QUEUE
        API3 --> WORKER
    end
    
    subgraph "Database Scaling"
        PRIMARY[Primary DB]
        REPLICA1[Read Replica 1]
        REPLICA2[Read Replica 2]
        
        API1 --> PRIMARY
        API2 --> REPLICA1
        API3 --> REPLICA2
    end
```

### Memory Management

```mermaid
graph LR
    subgraph "Memory Allocation Strategy"
        subgraph "Frontend"
            REACTMEM[React State]
            CACHEMEM[Cache Memory]
            BUFFERMEM[Buffer Memory]
        end
        
        subgraph "Backend"
            APPMEM[Application Memory]
            NETMEM[Network Objects]
            STATSMEM[Statistics Buffer]
        end
        
        subgraph "MCP Server"
            TOOLMEM[Tool Registry]
            RESMEM[Resource Cache]
            CONNMEM[Connection Pool]
        end
        
        subgraph "Cleanup Strategies"
            GC[Garbage Collection]
            PERIODIC[Periodic Cleanup]
            THRESHOLD[Memory Threshold]
        end
    end
    
    REACTMEM --> GC
    NETMEM --> PERIODIC
    STATSMEM --> THRESHOLD
    TOOLMEM --> GC
```

## Security Architecture

### Authentication & Authorization Flow

```mermaid
sequenceDiagram
    participant USER as User
    participant FE as Frontend
    participant API as Backend API
    participant AUTH as Auth Service
    participant DB as Database
    
    USER->>FE: Login Request
    FE->>API: Auth Request
    API->>AUTH: Validate Credentials
    AUTH->>DB: User Lookup
    DB-->>AUTH: User Data
    AUTH-->>API: JWT Token
    API-->>FE: Auth Response
    FE->>FE: Store Token
    
    Note over FE: Subsequent Requests
    FE->>API: API Request + JWT
    API->>AUTH: Validate Token
    AUTH-->>API: Token Valid
    API-->>FE: Protected Data
```

### Security Layers

```mermaid
graph TB
    subgraph "Security Architecture"
        subgraph "Network Security"
            FW[Firewall Rules]
            VPN[VPN Access]
            TLS[TLS Encryption]
        end
        
        subgraph "Application Security"
            JWT[JWT Authentication]
            RBAC[Role-Based Access]
            VALID[Input Validation]
        end
        
        subgraph "Infrastructure Security"
            CONT[Container Isolation]
            PRIV[Privilege Separation]
            AUDIT[Audit Logging]
        end
        
        subgraph "Data Security"
            ENCRYPT[Data Encryption]
            BACKUP[Secure Backups]
            KEYS[Key Management]
        end
    end
```

## Deployment Architecture

### Container Deployment

```mermaid
graph TB
    subgraph "Docker Deployment"
        subgraph "Application Containers"
            FRONTEND[Frontend Container]
            BACKEND[Backend Container]
            MCP[MCP Container]
        end
        
        subgraph "Service Containers"
            MONGO[MongoDB Container]
            REDIS[Redis Container]
            NGINX[Nginx Container]
        end
        
        subgraph "Networking"
            APPNET[App Network]
            DBNET[Database Network]
            EXTERNAL[External Network]
        end
        
        FRONTEND --- APPNET
        BACKEND --- APPNET
        MCP --- APPNET
        MONGO --- DBNET
        REDIS --- DBNET
        NGINX --- EXTERNAL
        
        APPNET --- DBNET
        APPNET --- EXTERNAL
    end
```

### High Availability Setup

```mermaid
graph TB
    subgraph "HA Deployment Architecture"
        subgraph "Load Balancer Tier"
            LB1[Primary LB]
            LB2[Backup LB]
        end
        
        subgraph "Application Tier"
            APP1[App Instance 1]
            APP2[App Instance 2]
            APP3[App Instance 3]
        end
        
        subgraph "Database Tier"
            DB1[Primary DB]
            DB2[Secondary DB]
            DB3[Arbiter]
        end
        
        subgraph "Storage Tier"
            SHARED[Shared Storage]
            BACKUP[Backup Storage]
        end
        
        LB1 --> APP1
        LB1 --> APP2
        LB2 --> APP3
        
        APP1 --> DB1
        APP2 --> DB2
        APP3 --> DB3
        
        DB1 --> SHARED
        DB2 --> SHARED
        SHARED --> BACKUP
    end
```

## System Integration

### External System Integration

```mermaid
graph LR
    subgraph "Mininet Web Framework"
        CORE[Core System]
    end
    
    subgraph "AI Services"
        OPENAI[OpenAI API]
        CLAUDE[Claude API]
        GEMINI[Gemini API]
        OLLAMA[Local Ollama]
    end
    
    subgraph "Monitoring Systems"
        PROM[Prometheus]
        GRAFANA[Grafana]
        ELASTIC[Elasticsearch]
    end
    
    subgraph "SDN Controllers"
        RYU[Ryu Controller]
        ODL[OpenDaylight]
        ONOS[ONOS Controller]
    end
    
    subgraph "Virtualization"
        DOCKER[Docker Engine]
        KUBE[Kubernetes]
        VM[Virtual Machines]
    end
    
    CORE --> OPENAI
    CORE --> CLAUDE
    CORE --> GEMINI
    CORE --> OLLAMA
    
    CORE --> PROM
    CORE --> GRAFANA
    CORE --> ELASTIC
    
    CORE --> RYU
    CORE --> ODL
    CORE --> ONOS
    
    CORE --> DOCKER
    CORE --> KUBE
    CORE --> VM
```

## Technology Stack Summary

### Frontend Stack
- **React** 18.2.0 - UI Framework
- **Tailwind CSS** 3.2.7 - Styling
- **Lucide React** - Icons
- **React Draggable** - Drag & Drop
- **JSON Editor** - Configuration

### Backend Stack
- **Flask** 2.3.3 - Web Framework
- **Python** 3.8+ - Runtime
- **Mininet** - Network Emulation
- **Ryu** - SDN Controller
- **MongoDB** - Database
- **PyYAML** - Configuration

### MCP Stack
- **FastMCP** 2.0+ - Protocol Implementation
- **HTTPX** - HTTP Client
- **Node.js** - Bridge Runtime
- **JSON-RPC** - Protocol Transport

### Infrastructure Stack
- **Docker** - Containerization
- **Nginx** - Reverse Proxy
- **systemd** - Service Management
- **Open vSwitch** - Virtual Switching
- **Linux** - Operating System

This comprehensive architecture enables scalable, maintainable, and extensible network simulation and management capabilities with modern web technologies and AI integration.