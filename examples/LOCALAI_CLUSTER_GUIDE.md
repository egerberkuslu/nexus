# LocalAI P2P Cluster in Mininet - Complete Guide

This guide explains how to set up and use LocalAI P2P clustering in your Mininet topology.

## 🎯 What is LocalAI P2P Clustering?

LocalAI P2P mode allows you to:
- **Distribute AI workloads** across multiple nodes (Raspberry Pis, servers, containers)
- **Share models** between nodes automatically
- **Load balance** inference requests across workers
- **Scale horizontally** by adding more worker nodes

## 🏗️ Architecture in Your Topology

```
┌─────────────────┐
│   Host Node     │  ← Coordinates workers, serves web UI
│  (mn.host-7a5e) │  ← Port 8080 (mapped to 32778)
│  LocalAI Host   │  ← Generates P2P token
└────────┬────────┘
         │ P2P Token
         ├─────────────────┬─────────────────┐
         │                 │                 │
┌────────▼────────┐ ┌──────▼──────┐ ┌──────▼──────┐
│   Worker 1      │ │  Worker 2   │ │  Worker N   │
│  (mn.host-1)    │ │(mn.host-8)  │ │   (...)     │
│  LocalAI Worker │ │LocalAI Wkr  │ │LocalAI Wkr  │
└─────────────────┘ └─────────────┘ └─────────────┘
```

## 🚀 Quick Start

### Method 1: Automated Setup (Recommended)

Use the provided script to automatically configure the cluster:

```bash
cd /home/ege/Desktop/cadeceus-flux-mininet-from-strach/caduceus-flux/examples
./localai-cluster-setup.sh
```

This script will:
1. Start LocalAI on the host node
2. Wait for P2P token generation
3. Extract the token automatically
4. Start workers with the token
5. Show you access URLs and status commands

### Method 2: Manual Setup

**Step 1: Start Host Node**
```bash
# Start LocalAI on host
docker exec -d mn.host-7a5e bash -c "PROFILE=cpu /aio/entrypoint.sh > /var/log/localai.log 2>&1"

# Wait 30 seconds for initialization
sleep 30
```

**Step 2: Get P2P Token**
```bash
# Extract token from host logs
docker exec mn.host-7a5e grep -A 5 "Generated Token" /var/log/localai.log
```

Copy the token (long string starting with `eyJ...`)

**Step 3: Start Workers**
```bash
# Worker 1
docker exec -d mn.host-1 bash -c "export TOKEN='<paste-token-here>' && export WORKER_ID='worker-1' && PROFILE=cpu /aio/entrypoint.sh > /var/log/localai.log 2>&1"

# Worker 2
docker exec -d mn.host-8 bash -c "export TOKEN='<paste-token-here>' && export WORKER_ID='worker-2' && PROFILE=cpu /aio/entrypoint.sh > /var/log/localai.log 2>&1"
```

## 🌐 Accessing the Web UI

Once the cluster is running (wait 10-15 minutes for model downloads):

**Access URLs:**
- Local: `http://localhost:32778`
- Network: `http://<your-host-ip>:32778`

**What You Can Do in the UI:**

### 1. Chat Interface
- Test AI text generation
- See responses distributed across workers
- Compare performance with/without clustering

### 2. Image Generation
- Create images with Stable Diffusion
- Workload automatically distributed to available workers

### 3. API Playground
- Test OpenAI-compatible API endpoints
- Try different models and parameters

### 4. Model Management
- View loaded models
- Load/unload models dynamically
- See model distribution across cluster

## 📊 Monitoring the Cluster

### Check Cluster Status
```bash
# Overall cluster stats
curl http://localhost:32778/api/p2p/stats

# List connected workers
curl http://localhost:32778/api/p2p/workers

# Available models
curl http://localhost:32778/v1/models
```

### View Logs
```bash
# Host node logs
docker exec mn.host-7a5e tail -f /var/log/localai.log

# Worker 1 logs
docker exec mn.host-1 tail -f /var/log/localai.log

# Worker 2 logs
docker exec mn.host-8 tail -f /var/log/localai.log
```

## 🧪 Testing the Cluster

### Test Text Generation
```bash
curl http://localhost:32778/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hermes-3",
    "messages": [{"role": "user", "content": "Explain P2P networking in 3 sentences"}]
  }'
```

### Test Image Generation
```bash
curl http://localhost:32778/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A futuristic network topology diagram",
    "size": "512x512"
  }'
```

### Check Worker Distribution
```bash
# See which workers handled requests
curl http://localhost:32778/api/p2p/stats | jq '.workers[] | {id: .id, requests: .requests_handled}'
```

## 🎮 Using the Web Interface

### 1. Chat Tab
- Open `http://localhost:32778`
- Go to **Chat** tab
- Select model (e.g., "hermes-3")
- Type your message
- **Watch**: Requests are distributed across workers automatically!

### 2. Images Tab
- Go to **Images** tab
- Enter a prompt
- Click **Generate**
- See the generated image (processed by cluster)

### 3. Models Tab
- View all available models
- See which models are loaded
- Download new models from HuggingFace

### 4. Settings Tab
- Configure cluster behavior
- Set worker preferences
- Adjust model parameters

## 📈 Performance Benefits

**Without P2P (Single Node):**
- Request → Single node processes → Response
- Limited by single node's resources

**With P2P Cluster:**
- Request → Load balancer → Available worker → Response
- Scales with number of workers
- Automatic failover if worker is busy

## 🔧 Troubleshooting

### Workers Not Connecting
```bash
# 1. Check token is correct
docker exec mn.host-1 env | grep TOKEN

# 2. Check worker logs for errors
docker exec mn.host-1 tail -100 /var/log/localai.log | grep -i error

# 3. Verify network connectivity
docker exec mn.host-1 ping -c 3 mn.host-7a5e
```

### Web UI Not Loading
```bash
# 1. Check if host is serving
curl -I http://localhost:32778/

# 2. Check host logs
docker exec mn.host-7a5e tail -50 /var/log/localai.log | grep -i "listening"

# 3. Verify port mapping
docker ps | grep mn.host-7a5e
```

### Models Still Downloading
```bash
# Check download progress
docker exec mn.host-7a5e ls -lh /models/*.partial

# Monitor download
docker exec mn.host-7a5e tail -f /var/log/localai.log | grep -i downloading
```

## 🎯 Next Steps

1. **Wait for downloads** (~15-20 min first time)
2. **Access web UI** at `http://localhost:32778`
3. **Test chat** with the distributed cluster
4. **Generate images** using Stable Diffusion
5. **Monitor performance** with API stats
6. **Add more workers** to scale horizontally

## 📚 Useful Commands Reference

```bash
# Cluster setup
./examples/localai-cluster-setup.sh

# Check all containers
docker ps | grep mn.

# Stop cluster
docker exec mn.host-7a5e pkill local-ai
docker exec mn.host-1 pkill local-ai
docker exec mn.host-8 pkill local-ai

# Restart cluster
./examples/localai-cluster-setup.sh

# View real-time stats
watch -n 2 'curl -s http://localhost:32778/api/p2p/stats | jq'
```

## 🌟 Example Use Cases

1. **Distributed Text Generation**: Chat requests load-balanced across Raspberry Pis
2. **Image Generation Farm**: Stable Diffusion images processed in parallel
3. **Edge AI Network**: LocalAI running on network edge devices
4. **Fault-Tolerant Inference**: Automatic failover if workers go offline
5. **Resource Sharing**: Small models on edge, large models on powerful workers

---

**Happy clustering! 🚀**

For more information:
- LocalAI Docs: https://localai.io/
- P2P Mode: https://localai.io/features/p2p/
