-- Add new device types to the devicetype enum
ALTER TYPE devicetype ADD VALUE IF NOT EXISTS 'container';
ALTER TYPE devicetype ADD VALUE IF NOT EXISTS 'p4switch';
ALTER TYPE devicetype ADD VALUE IF NOT EXISTS 'controller';

-- Update station from 'sta' to 'station' if needed
-- Note: This is complex and requires a temp column approach if the value is already in use

