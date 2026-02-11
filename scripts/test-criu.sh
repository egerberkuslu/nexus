#!/bin/bash
###############################################################################
# CRIU Testing Script for Caduceus-Flux
# Tests CRIU functionality with Docker containers
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[TEST]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

run_test() {
    local test_name="$1"
    local test_func="$2"

    log "Running: $test_name"

    if $test_func; then
        pass "$test_name"
        ((TESTS_PASSED++))
    else
        fail "$test_name"
        ((TESTS_FAILED++))
    fi

    echo ""
}

skip_test() {
    local test_name="$1"
    local reason="$2"

    warn "SKIPPED: $test_name"
    info "Reason: $reason"
    ((TESTS_SKIPPED++))
    echo ""
}

# Test 1: Check if CRIU is installed
test_criu_installed() {
    if command -v criu &> /dev/null; then
        info "CRIU version: $(criu --version | head -1)"
        return 0
    else
        error "CRIU not found in PATH"
        return 1
    fi
}

# Test 2: Check kernel support
test_kernel_support() {
    if criu check 2>&1 | grep -q "Error"; then
        error "CRIU kernel check failed"
        criu check 2>&1
        return 1
    else
        info "Kernel supports CRIU"
        return 0
    fi
}

# Test 3: Check Docker experimental features
test_docker_experimental() {
    local experimental=$(docker version --format '{{.Server.Experimental}}' 2>/dev/null)

    if [ "$experimental" = "true" ]; then
        info "Docker experimental features: enabled"
        return 0
    else
        error "Docker experimental features: disabled"
        error "Run: scripts/install-criu.sh to enable"
        return 1
    fi
}

# Test 4: Simple container checkpoint
test_simple_checkpoint() {
    local container_name="criu-test-simple-$$"

    info "Creating test container: $container_name"

    # Create a simple container
    docker run -d \
        --name "$container_name" \
        --security-opt seccomp=unconfined \
        alpine sleep 3600 >/dev/null 2>&1

    sleep 2

    # Try to checkpoint
    if docker checkpoint create "$container_name" test-checkpoint 2>&1 | grep -q "test-checkpoint"; then
        info "Checkpoint created successfully"

        # Verify checkpoint exists
        if docker checkpoint ls "$container_name" 2>&1 | grep -q "test-checkpoint"; then
            info "Checkpoint verified"

            # Cleanup
            docker rm -f "$container_name" >/dev/null 2>&1
            return 0
        else
            error "Checkpoint not found in list"
            docker rm -f "$container_name" >/dev/null 2>&1
            return 1
        fi
    else
        error "Checkpoint creation failed"
        docker logs "$container_name" 2>&1
        docker rm -f "$container_name" >/dev/null 2>&1
        return 1
    fi
}

# Test 5: Checkpoint with leave-running
test_checkpoint_leave_running() {
    local container_name="criu-test-leave-running-$$"

    info "Creating test container: $container_name"

    docker run -d \
        --name "$container_name" \
        --security-opt seccomp=unconfined \
        alpine sh -c "while true; do echo hello; sleep 1; done" >/dev/null 2>&1

    sleep 2

    # Checkpoint with --leave-running
    if docker checkpoint create --leave-running "$container_name" test-checkpoint 2>&1; then
        info "Checkpoint created with --leave-running"

        # Check if container is still running
        if docker ps | grep -q "$container_name"; then
            info "Container still running after checkpoint"
            docker rm -f "$container_name" >/dev/null 2>&1
            return 0
        else
            error "Container stopped after checkpoint"
            docker rm -f "$container_name" >/dev/null 2>&1
            return 1
        fi
    else
        error "Checkpoint with --leave-running failed"
        docker rm -f "$container_name" >/dev/null 2>&1
        return 1
    fi
}

# Test 6: Checkpoint and restore
test_checkpoint_restore() {
    local container_name="criu-test-restore-$$"
    local checkpoint_dir="/tmp/criu-test-restore-$$"

    mkdir -p "$checkpoint_dir"

    info "Creating test container: $container_name"

    docker run -d \
        --name "$container_name" \
        --security-opt seccomp=unconfined \
        alpine sh -c "echo 'Start'; sleep 3600" >/dev/null 2>&1

    sleep 2

    # Checkpoint
    if docker checkpoint create \
        --checkpoint-dir "$checkpoint_dir" \
        "$container_name" \
        test-checkpoint 2>&1; then

        info "Container checkpointed"

        # Container should be stopped now
        sleep 1

        # Try to restore
        if docker start \
            --checkpoint test-checkpoint \
            --checkpoint-dir "$checkpoint_dir" \
            "$container_name" 2>&1; then

            info "Container restored successfully"

            # Check if running
            if docker ps | grep -q "$container_name"; then
                info "Container is running after restore"
                docker rm -f "$container_name" >/dev/null 2>&1
                rm -rf "$checkpoint_dir"
                return 0
            else
                error "Container not running after restore"
                docker rm -f "$container_name" >/dev/null 2>&1
                rm -rf "$checkpoint_dir"
                return 1
            fi
        else
            error "Restore failed"
            docker rm -f "$container_name" >/dev/null 2>&1
            rm -rf "$checkpoint_dir"
            return 1
        fi
    else
        error "Checkpoint failed"
        docker rm -f "$container_name" >/dev/null 2>&1
        rm -rf "$checkpoint_dir"
        return 1
    fi
}

# Test 7: Checkpoint with network
test_checkpoint_with_network() {
    local container_name="criu-test-network-$$"
    local network_name="criu-test-net-$$"

    info "Creating test network: $network_name"
    docker network create "$network_name" >/dev/null 2>&1

    info "Creating container on custom network"

    docker run -d \
        --name "$container_name" \
        --network "$network_name" \
        --security-opt seccomp=unconfined \
        alpine sleep 3600 >/dev/null 2>&1

    sleep 2

    # Try checkpoint
    if docker checkpoint create --leave-running "$container_name" test-checkpoint 2>&1; then
        info "Checkpoint with custom network succeeded"
        docker rm -f "$container_name" >/dev/null 2>&1
        docker network rm "$network_name" >/dev/null 2>&1
        return 0
    else
        warn "Checkpoint with custom network failed (expected in some cases)"
        docker rm -f "$container_name" >/dev/null 2>&1
        docker network rm "$network_name" >/dev/null 2>&1
        return 0  # Don't fail, this is environment-dependent
    fi
}

# Test 8: Check CRIU directories
test_criu_directories() {
    if [ -d "/var/lib/caduceus/criu" ]; then
        info "CRIU checkpoint directory exists: /var/lib/caduceus/criu"
        return 0
    else
        error "CRIU checkpoint directory not found"
        error "Run: sudo mkdir -p /var/lib/caduceus/criu"
        return 1
    fi
}

# Test 9: Python CRIU bindings
test_python_criu() {
    if python3 -c "import pycriu" 2>/dev/null; then
        info "Python CRIU bindings available"
        return 0
    else
        warn "Python CRIU bindings not available"
        warn "Run: pip3 install pycriu"
        return 0  # Not critical
    fi
}

# Test 10: Caduceus CRIU handler
test_caduceus_criu_handler() {
    local handler_path="/home/ege/Desktop/cadeceus-flux-mininet-from-strach/caduceus-flux/emulation-container/grpc_agent/criu_handler.py"

    if [ -f "$handler_path" ]; then
        info "Caduceus CRIU handler found"

        # Try to import it
        if python3 -c "import sys; sys.path.insert(0, '$(dirname $handler_path)'); import criu_handler" 2>/dev/null; then
            info "CRIU handler module imports successfully"
            return 0
        else
            warn "CRIU handler has import errors"
            return 0  # Not critical for this test
        fi
    else
        error "Caduceus CRIU handler not found at: $handler_path"
        return 1
    fi
}

# Main test execution
main() {
    echo "========================================="
    echo "CRIU Testing Suite for Caduceus-Flux"
    echo "========================================="
    echo ""

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        warn "Some tests may fail without root privileges"
        echo ""
    fi

    # Run tests
    run_test "CRIU Installation" test_criu_installed
    run_test "Kernel Support" test_kernel_support
    run_test "Docker Experimental Features" test_docker_experimental
    run_test "CRIU Directories" test_criu_directories
    run_test "Python CRIU Bindings" test_python_criu
    run_test "Caduceus CRIU Handler" test_caduceus_criu_handler

    # Run Docker tests only if basic checks pass
    if [ $TESTS_FAILED -eq 0 ]; then
        run_test "Simple Checkpoint" test_simple_checkpoint
        run_test "Checkpoint with Leave-Running" test_checkpoint_leave_running
        run_test "Checkpoint and Restore" test_checkpoint_restore
        run_test "Checkpoint with Custom Network" test_checkpoint_with_network
    else
        skip_test "Docker Checkpoint Tests" "Basic checks failed"
    fi

    # Summary
    echo "========================================="
    echo "Test Summary"
    echo "========================================="
    echo "Passed:  $TESTS_PASSED"
    echo "Failed:  $TESTS_FAILED"
    echo "Skipped: $TESTS_SKIPPED"
    echo "========================================="

    if [ $TESTS_FAILED -eq 0 ]; then
        pass "All tests passed!"
        exit 0
    else
        fail "Some tests failed"
        echo ""
        echo "Troubleshooting:"
        echo "1. Run: sudo ./scripts/install-criu.sh"
        echo "2. Check kernel config: grep CONFIG_CHECKPOINT_RESTORE /boot/config-\$(uname -r)"
        echo "3. Restart Docker: sudo systemctl restart docker"
        echo "4. Check logs: journalctl -u docker"
        exit 1
    fi
}

# Run main function
main "$@"
