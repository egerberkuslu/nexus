-- Migration: Add dynamic container tracking fields to topologies table
-- Date: 2025-11-04
-- Description: Adds fields needed for tracking dynamically spawned emulation containers

-- Add container tracking fields to topologies table
ALTER TABLE topologies
ADD COLUMN IF NOT EXISTS container_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS container_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS container_port INTEGER,
ADD COLUMN IF NOT EXISTS container_ip VARCHAR(45),
ADD COLUMN IF NOT EXISTS container_status VARCHAR(50) DEFAULT 'not_created';

-- Create index for faster container lookups
CREATE INDEX IF NOT EXISTS idx_topologies_container_id ON topologies(container_id);
CREATE INDEX IF NOT EXISTS idx_topologies_container_status ON topologies(container_status);

-- Add comments for documentation
COMMENT ON COLUMN topologies.container_id IS 'Docker container ID for this topology emulation';
COMMENT ON COLUMN topologies.container_name IS 'Human-readable container name';
COMMENT ON COLUMN topologies.container_port IS 'gRPC port for this container (50051-50151 range)';
COMMENT ON COLUMN topologies.container_ip IS 'Container IP address in Docker network';
COMMENT ON COLUMN topologies.container_status IS 'Container lifecycle status: not_created, creating, running, stopped, failed';
