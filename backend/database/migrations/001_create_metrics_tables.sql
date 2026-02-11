-- Caduceus-Flux Metrics Database Schema
-- Creates tables for storing network metrics from Kafka stream

-- Enable TimescaleDB extension (if available) for better time-series performance.
-- The base Postgres image may not ship the extension, so we guard all Timescale-specific statements.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE';
    END IF;
END $$;

-- ============================================================================
-- Main Metrics Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS network_metrics (
    id BIGSERIAL,
    device VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Traffic Metrics
    bytes_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0,
    packets_sent BIGINT DEFAULT 0,
    packets_received BIGINT DEFAULT 0,

    -- Error Metrics
    errors_in BIGINT DEFAULT 0,
    errors_out BIGINT DEFAULT 0,
    drops_in BIGINT DEFAULT 0,
    drops_out BIGINT DEFAULT 0,

    -- System Metrics
    cpu_percent DOUBLE PRECISION DEFAULT 0,
    memory_percent DOUBLE PRECISION DEFAULT 0,

    -- Metadata
    source VARCHAR(100) DEFAULT 'kafka-connect',

    PRIMARY KEY (device, timestamp)
);

-- Create hypertable for time-series optimization (only if TimescaleDB is installed)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'create_hypertable') THEN
        PERFORM create_hypertable(
            'network_metrics',
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_network_metrics_device ON network_metrics(device);
CREATE INDEX IF NOT EXISTS idx_network_metrics_timestamp ON network_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_network_metrics_device_timestamp ON network_metrics(device, timestamp DESC);

-- ============================================================================
-- Interface Metrics Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS interface_metrics (
    id BIGSERIAL,
    device VARCHAR(255) NOT NULL,
    interface VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Interface Statistics
    rx_bytes BIGINT DEFAULT 0,
    tx_bytes BIGINT DEFAULT 0,
    rx_packets BIGINT DEFAULT 0,
    tx_packets BIGINT DEFAULT 0,
    rx_errors BIGINT DEFAULT 0,
    tx_errors BIGINT DEFAULT 0,
    rx_dropped BIGINT DEFAULT 0,
    tx_dropped BIGINT DEFAULT 0,

    -- Status
    status VARCHAR(20) DEFAULT 'unknown',
    mtu INTEGER,

    PRIMARY KEY (device, interface, timestamp)
);

-- Create hypertable (only if TimescaleDB is installed)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'create_hypertable') THEN
        PERFORM create_hypertable(
            'interface_metrics',
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_interface_metrics_device_iface ON interface_metrics(device, interface);
CREATE INDEX IF NOT EXISTS idx_interface_metrics_timestamp ON interface_metrics(timestamp DESC);

-- ============================================================================
-- Protocol Metrics Table (OSPF, BGP, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS protocol_metrics (
    id BIGSERIAL,
    device VARCHAR(255) NOT NULL,
    protocol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Protocol-specific metrics
    neighbor_count INTEGER DEFAULT 0,
    route_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'unknown',

    -- Additional metrics (JSON for flexibility)
    metrics_json JSONB,

    PRIMARY KEY (device, protocol, timestamp)
);

-- Create hypertable (only if TimescaleDB is installed)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'create_hypertable') THEN
        PERFORM create_hypertable(
            'protocol_metrics',
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_protocol_metrics_device ON protocol_metrics(device);
CREATE INDEX IF NOT EXISTS idx_protocol_metrics_protocol ON protocol_metrics(protocol);
CREATE INDEX IF NOT EXISTS idx_protocol_metrics_json ON protocol_metrics USING GIN(metrics_json);

-- ============================================================================
-- Flow Table Metrics (OpenFlow switches)
-- ============================================================================

CREATE TABLE IF NOT EXISTS flow_metrics (
    id BIGSERIAL,
    switch VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Flow statistics
    flow_count INTEGER DEFAULT 0,
    total_packet_count BIGINT DEFAULT 0,
    total_byte_count BIGINT DEFAULT 0,

    -- Flow details (JSON array of flow entries)
    flows_json JSONB,

    PRIMARY KEY (switch, timestamp)
);

-- Create hypertable (only if TimescaleDB is installed)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'create_hypertable') THEN
        PERFORM create_hypertable(
            'flow_metrics',
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_flow_metrics_switch ON flow_metrics(switch);
CREATE INDEX IF NOT EXISTS idx_flow_metrics_timestamp ON flow_metrics(timestamp DESC);

-- ============================================================================
-- Aggregated Metrics (for ML training and analytics)
-- ============================================================================

CREATE TABLE IF NOT EXISTS metrics_aggregated_1min (
    device VARCHAR(255) NOT NULL,
    time_bucket TIMESTAMPTZ NOT NULL,

    -- Aggregated traffic
    avg_bytes_sent DOUBLE PRECISION,
    avg_bytes_received DOUBLE PRECISION,
    max_bytes_sent BIGINT,
    max_bytes_received BIGINT,
    total_packets_sent BIGINT,
    total_packets_received BIGINT,

    -- Aggregated errors
    total_errors_in BIGINT,
    total_errors_out BIGINT,
    total_drops_in BIGINT,
    total_drops_out BIGINT,

    -- Aggregated system metrics
    avg_cpu_percent DOUBLE PRECISION,
    max_cpu_percent DOUBLE PRECISION,
    avg_memory_percent DOUBLE PRECISION,
    max_memory_percent DOUBLE PRECISION,

    -- Sample count
    sample_count INTEGER,

    PRIMARY KEY (device, time_bucket)
);

-- Create hypertable (only if TimescaleDB is installed)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'create_hypertable') THEN
        PERFORM create_hypertable(
            'metrics_aggregated_1min',
            'time_bucket',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- ============================================================================
-- Continuous Aggregates (automated roll-ups)
-- ============================================================================

-- 1-minute aggregation view (TimescaleDB-only: uses time_bucket + continuous aggregates)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'time_bucket') THEN
        EXECUTE $sql$
            CREATE MATERIALIZED VIEW IF NOT EXISTS metrics_1min
            WITH (timescaledb.continuous) AS
            SELECT
                device,
                time_bucket('1 minute', timestamp) AS time_bucket,
                AVG(bytes_sent) AS avg_bytes_sent,
                AVG(bytes_received) AS avg_bytes_received,
                MAX(bytes_sent) AS max_bytes_sent,
                MAX(bytes_received) AS max_bytes_received,
                SUM(packets_sent) AS total_packets_sent,
                SUM(packets_received) AS total_packets_received,
                SUM(errors_in) AS total_errors_in,
                SUM(errors_out) AS total_errors_out,
                SUM(drops_in) AS total_drops_in,
                SUM(drops_out) AS total_drops_out,
                AVG(cpu_percent) AS avg_cpu_percent,
                MAX(cpu_percent) AS max_cpu_percent,
                AVG(memory_percent) AS avg_memory_percent,
                MAX(memory_percent) AS max_memory_percent,
                COUNT(*) AS sample_count
            FROM network_metrics
            GROUP BY device, time_bucket
        $sql$;

        IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'add_continuous_aggregate_policy') THEN
            PERFORM add_continuous_aggregate_policy(
                'metrics_1min',
                start_offset => INTERVAL '2 hours',
                end_offset => INTERVAL '1 minute',
                schedule_interval => INTERVAL '1 minute',
                if_not_exists => TRUE
            );
        END IF;
    END IF;
END $$;

-- 5-minute aggregation view (TimescaleDB-only: uses time_bucket + continuous aggregates)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'time_bucket') THEN
        EXECUTE $sql$
            CREATE MATERIALIZED VIEW IF NOT EXISTS metrics_5min
            WITH (timescaledb.continuous) AS
            SELECT
                device,
                time_bucket('5 minutes', timestamp) AS time_bucket,
                AVG(bytes_sent) AS avg_bytes_sent,
                AVG(bytes_received) AS avg_bytes_received,
                MAX(bytes_sent) AS max_bytes_sent,
                MAX(bytes_received) AS max_bytes_received,
                SUM(packets_sent) AS total_packets_sent,
                SUM(packets_received) AS total_packets_received,
                AVG(cpu_percent) AS avg_cpu_percent,
                MAX(cpu_percent) AS max_cpu_percent,
                COUNT(*) AS sample_count
            FROM network_metrics
            GROUP BY device, time_bucket
        $sql$;

        IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'add_continuous_aggregate_policy') THEN
            PERFORM add_continuous_aggregate_policy(
                'metrics_5min',
                start_offset => INTERVAL '12 hours',
                end_offset => INTERVAL '5 minutes',
                schedule_interval => INTERVAL '5 minutes',
                if_not_exists => TRUE
            );
        END IF;
    END IF;
END $$;

-- ============================================================================
-- Data Retention Policies
-- ============================================================================

-- Retention policies (TimescaleDB-only)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'add_retention_policy') THEN
        PERFORM add_retention_policy('network_metrics', INTERVAL '7 days', if_not_exists => TRUE);
        PERFORM add_retention_policy('interface_metrics', INTERVAL '7 days', if_not_exists => TRUE);
        PERFORM add_retention_policy('protocol_metrics', INTERVAL '7 days', if_not_exists => TRUE);
        PERFORM add_retention_policy('flow_metrics', INTERVAL '7 days', if_not_exists => TRUE);
        PERFORM add_retention_policy('metrics_1min', INTERVAL '30 days', if_not_exists => TRUE);
        PERFORM add_retention_policy('metrics_5min', INTERVAL '90 days', if_not_exists => TRUE);
    END IF;
END $$;

-- ============================================================================
-- ML Training Features Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS ml_training_features (
    id BIGSERIAL PRIMARY KEY,
    device VARCHAR(255) NOT NULL,
    time_window_start TIMESTAMPTZ NOT NULL,
    time_window_end TIMESTAMPTZ NOT NULL,

    -- Traffic features
    avg_throughput_mbps DOUBLE PRECISION,
    max_throughput_mbps DOUBLE PRECISION,
    min_throughput_mbps DOUBLE PRECISION,
    std_throughput_mbps DOUBLE PRECISION,

    -- Packet features
    packet_rate_avg DOUBLE PRECISION,
    packet_rate_max DOUBLE PRECISION,
    packet_loss_rate DOUBLE PRECISION,
    error_rate DOUBLE PRECISION,

    -- System features
    cpu_avg DOUBLE PRECISION,
    cpu_max DOUBLE PRECISION,
    memory_avg DOUBLE PRECISION,
    memory_max DOUBLE PRECISION,

    -- Labels (for supervised learning)
    congestion_level INTEGER, -- 0: normal, 1: medium, 2: high
    anomaly_detected BOOLEAN DEFAULT FALSE,

    -- Metadata
    feature_version VARCHAR(20) DEFAULT '1.0',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for ML queries
CREATE INDEX IF NOT EXISTS idx_ml_features_device ON ml_training_features(device);
CREATE INDEX IF NOT EXISTS idx_ml_features_time_window ON ml_training_features(time_window_start, time_window_end);
CREATE INDEX IF NOT EXISTS idx_ml_features_congestion ON ml_training_features(congestion_level);

-- ============================================================================
-- Utility Functions
-- ============================================================================

-- Function to calculate throughput in Mbps
CREATE OR REPLACE FUNCTION calculate_throughput_mbps(bytes BIGINT, interval_seconds INTEGER)
RETURNS DOUBLE PRECISION AS $$
BEGIN
    RETURN (bytes * 8.0) / (interval_seconds * 1000000.0);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to get latest metrics for a device
CREATE OR REPLACE FUNCTION get_latest_metrics(p_device VARCHAR(255))
RETURNS TABLE (
    device VARCHAR(255),
    metric_timestamp TIMESTAMPTZ,
    bytes_sent BIGINT,
    bytes_received BIGINT,
    cpu_percent DOUBLE PRECISION,
    memory_percent DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        nm.device,
        nm.timestamp AS metric_timestamp,
        nm.bytes_sent,
        nm.bytes_received,
        nm.cpu_percent,
        nm.memory_percent
    FROM network_metrics nm
    WHERE nm.device = p_device
    ORDER BY nm.timestamp DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Grants
-- ============================================================================

-- Grant access to caduceus user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO caduceus;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO caduceus;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO caduceus;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE network_metrics IS 'Main table for storing network device metrics from Kafka stream';
COMMENT ON TABLE interface_metrics IS 'Detailed interface-level metrics';
COMMENT ON TABLE protocol_metrics IS 'Routing protocol metrics (OSPF, BGP, etc.)';
COMMENT ON TABLE flow_metrics IS 'OpenFlow switch flow table metrics';
COMMENT ON TABLE ml_training_features IS 'Engineered features for machine learning training';

-- ============================================================================
-- Initial Statistics
-- ============================================================================

-- Analyze tables for query optimization
ANALYZE network_metrics;
ANALYZE interface_metrics;
ANALYZE protocol_metrics;
ANALYZE flow_metrics;
ANALYZE ml_training_features;

-- Print summary
DO $$
BEGIN
    RAISE NOTICE '✅ Metrics database schema created successfully';
    RAISE NOTICE '📊 Tables: network_metrics, interface_metrics, protocol_metrics, flow_metrics, ml_training_features';
    RAISE NOTICE '⏰ Continuous aggregates: metrics_1min, metrics_5min';
    RAISE NOTICE '🗑️  Retention policies: 7 days (raw), 30 days (1min agg), 90 days (5min agg)';
END $$;
