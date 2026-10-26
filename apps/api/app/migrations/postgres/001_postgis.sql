-- PostGIS: geometry for wards and reports, spatial indexes (Postgres only).
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS wards (
    ward_id TEXT PRIMARY KEY,
    ward_name TEXT NOT NULL,
    population_est DOUBLE PRECISION,
    area_km2 DOUBLE PRECISION,
    geom geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wards_geom ON wards USING GIST (geom);

ALTER TABLE reports ADD COLUMN IF NOT EXISTS geom geography(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography) STORED;
CREATE INDEX IF NOT EXISTS idx_reports_geom ON reports USING GIST (geom);

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS geom geography(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography) STORED;
CREATE INDEX IF NOT EXISTS idx_tasks_geom ON tasks USING GIST (geom);
