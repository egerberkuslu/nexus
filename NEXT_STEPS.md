# CRIU Setup - Next Steps

## Current Status

✅ **Snapshot service code fixed** - CRIU detection enabled
✅ **Dockerfile updated** - CRIU packages added
🔄 **Container building** - Currently in progress (5-10 minutes)

## What to Do

### Step 1: Wait for Build to Complete

The Docker container is currently building with CRIU support. This takes 5-10 minutes.

**Check build status:**
```bash
./CHECK_BUILD_STATUS.sh
```

Or manually:
```bash
ps aux | grep "docker build.*Dockerfile.simple"
```

### Step 2: Run the Complete Setup Script

Once the build is done, run ONE command:

```bash
sudo bash COMPLETE_CRIU_SETUP.sh
```

This will:
- ✓ Enable Docker experimental features
- ✓ Rebuild snapshot service
- ✓ Restart all services
- ✓ Verify CRIU is working

**Enter your sudo password when prompted.**

### Step 3: Verify CRIU Works

After running the setup script, check the frontend:

1. Open: http://localhost:3000
2. Create/start a topology
3. Go to **Snapshots** page
4. Click **Create Snapshot**
5. You should now see:
   - ✅ CRIU Live (~300MB) - **Available**
   - ✅ Hybrid Full (~700MB) - **Available**

## Alternative: Manual Steps

If you prefer to run steps manually:

```bash
# 1. Enable Docker experimental features
sudo ./enable-docker-experimental.sh

# 2. Wait for container build to finish
./CHECK_BUILD_STATUS.sh

# 3. Rebuild snapshot service
docker-compose build snapshot-service

# 4. Restart services
docker-compose down
docker-compose up -d

# 5. Wait 30 seconds for services to start
sleep 30

# 6. Verify
curl http://localhost:8006/api/snapshots/types | jq '.criu_available'
```

## Troubleshooting

### Build Taking Too Long

```bash
# Check if build is running
ps aux | grep docker | grep build

# If stuck, cancel and rebuild:
pkill -f "docker build"
cd emulation-container
docker build -f Dockerfile.simple -t caduceus-flux-emulation-container:latest .
```

### CRIU Still Shows Unavailable

1. Check Docker experimental mode:
   ```bash
   docker version --format '{{.Server.Experimental}}'
   # Should show: true
   ```

2. Check CRIU in image:
   ```bash
   docker run --rm --entrypoint bash caduceus-flux-emulation-container:latest -c "dpkg -l | grep criu"
   ```

3. Check snapshot service logs:
   ```bash
   docker-compose logs snapshot-service | grep -i criu
   ```

### Services Won't Start

```bash
# Check for errors
docker-compose ps
docker-compose logs --tail=50

# Force recreate
docker-compose down -v
docker-compose up -d
```

## Files Created

- `COMPLETE_CRIU_SETUP.sh` - Main setup script (run with sudo)
- `CHECK_BUILD_STATUS.sh` - Check if build is complete
- `enable-docker-experimental.sh` - Enable Docker experimental mode
- `CRIU_SETUP_GUIDE.md` - Detailed documentation
- `NEXT_STEPS.md` - This file

## Quick Reference

```bash
# Check build status
./CHECK_BUILD_STATUS.sh

# Run complete setup (after build finishes)
sudo bash COMPLETE_CRIU_SETUP.sh

# Verify CRIU is enabled
curl http://localhost:8006/api/snapshots/types | jq

# Check logs
docker-compose logs snapshot-service | tail -50
```

## Expected Result

After setup, when you create a snapshot, you'll see:

| Snapshot Type | Before | After |
|--------------|--------|-------|
| CRIU Live | ❌ Not available | ✅ Available (~300MB) |
| Hybrid Full | ❌ Not available | ✅ Available (~700MB) |

## Need Help?

See `CRIU_SETUP_GUIDE.md` for detailed troubleshooting and architecture information.
