BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 897e3940acf9

CREATE TABLE disruption_index (
    id UUID NOT NULL, 
    region_id UUID NOT NULL, 
    window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
    window_end TIMESTAMP WITH TIME ZONE NOT NULL, 
    flight_anomaly_score FLOAT NOT NULL, 
    event_relevance_score FLOAT NOT NULL, 
    airspace_score FLOAT NOT NULL, 
    airport_activity_score FLOAT NOT NULL, 
    satellite_score FLOAT NOT NULL, 
    weather_score FLOAT NOT NULL, 
    composite_index FLOAT NOT NULL, 
    severity_label VARCHAR(50) NOT NULL, 
    confidence_pct FLOAT NOT NULL, 
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_disruption_index_region_id ON disruption_index (region_id);

CREATE TABLE forecasts (
    id UUID NOT NULL, 
    region_id UUID NOT NULL, 
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    horizon_hours INTEGER NOT NULL, 
    metric_name VARCHAR(100) NOT NULL, 
    predicted_values JSONB NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE regions (
    id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    geom geometry(POLYGON,4326) NOT NULL, 
    centroid geometry(POINT,4326) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE INDEX idx_regions_centroid ON regions USING gist (centroid);

CREATE INDEX idx_regions_geom ON regions USING gist (geom);

CREATE INDEX idx_regions_centroid ON regions USING gist (centroid);

CREATE INDEX idx_regions_geom ON regions USING gist (geom);

CREATE TABLE satellites (
    id UUID NOT NULL, 
    norad_id INTEGER NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    tle_line1 VARCHAR(200), 
    tle_line2 VARCHAR(200), 
    PRIMARY KEY (id), 
    UNIQUE (norad_id)
);

CREATE TABLE what_changed_reports (
    id UUID NOT NULL, 
    region_id UUID NOT NULL, 
    event_id UUID NOT NULL, 
    before_start TIMESTAMP WITH TIME ZONE NOT NULL, 
    before_end TIMESTAMP WITH TIME ZONE NOT NULL, 
    after_start TIMESTAMP WITH TIME ZONE NOT NULL, 
    after_end TIMESTAMP WITH TIME ZONE NOT NULL, 
    metrics_json JSONB NOT NULL, 
    ai_explanation TEXT NOT NULL, 
    confidence_pct FLOAT NOT NULL, 
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE airports (
    id UUID NOT NULL, 
    iata_code VARCHAR(10) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    geom geometry(POINT,4326) NOT NULL, 
    region_id UUID, 
    PRIMARY KEY (id), 
    FOREIGN KEY(region_id) REFERENCES regions (id), 
    UNIQUE (iata_code)
);

CREATE INDEX idx_airports_geom ON airports USING gist (geom);

CREATE INDEX idx_airports_geom ON airports USING gist (geom);

CREATE TABLE events (
    id UUID NOT NULL, 
    external_id VARCHAR(100), 
    event_date TIMESTAMP WITH TIME ZONE NOT NULL, 
    event_type VARCHAR(100) NOT NULL, 
    category VARCHAR(100) NOT NULL, 
    severity VARCHAR(50) NOT NULL, 
    position geometry(POINT,4326) NOT NULL, 
    region_id UUID NOT NULL, 
    description TEXT, 
    source VARCHAR(50) NOT NULL, 
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(region_id) REFERENCES regions (id)
);

CREATE INDEX idx_events_position ON events USING gist (position);

CREATE INDEX idx_events_position ON events USING gist (position);

CREATE INDEX ix_events_position ON events USING gist (position);

CREATE INDEX ix_events_region_id_event_date ON events (region_id, event_date);

CREATE TABLE satellite_observations (
    id UUID NOT NULL, 
    satellite_id UUID NOT NULL, 
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
    position geometry(POINTZ,4326) NOT NULL, 
    altitude_km FLOAT NOT NULL, 
    source VARCHAR(50) NOT NULL, 
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(satellite_id) REFERENCES satellites (id)
);

CREATE INDEX idx_satellite_observations_position ON satellite_observations USING gist (position);

CREATE INDEX idx_satellite_observations_position ON satellite_observations USING gist (position);

CREATE INDEX ix_satellite_observations_position ON satellite_observations USING gist (position);

CREATE TABLE weather_observations (
    id UUID NOT NULL, 
    region_id UUID NOT NULL, 
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
    position geometry(POINT,4326) NOT NULL, 
    wind_speed_kt FLOAT NOT NULL, 
    precipitation_mm FLOAT NOT NULL, 
    storm_index FLOAT NOT NULL, 
    source VARCHAR(50) NOT NULL, 
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(region_id) REFERENCES regions (id)
);

CREATE INDEX idx_weather_observations_position ON weather_observations USING gist (position);

CREATE INDEX idx_weather_observations_position ON weather_observations USING gist (position);

CREATE INDEX ix_weather_observations_position ON weather_observations USING gist (position);

CREATE TABLE flight_routes (
    id UUID NOT NULL, 
    origin_airport_id UUID NOT NULL, 
    dest_airport_id UUID NOT NULL, 
    region_id UUID, 
    PRIMARY KEY (id), 
    FOREIGN KEY(dest_airport_id) REFERENCES airports (id), 
    FOREIGN KEY(origin_airport_id) REFERENCES airports (id), 
    FOREIGN KEY(region_id) REFERENCES regions (id)
);

CREATE INDEX ix_flight_routes_region_id ON flight_routes (region_id);

CREATE TABLE flight_observations (
    id UUID NOT NULL, 
    route_id UUID, 
    callsign VARCHAR(64) NOT NULL, 
    icao24 VARCHAR(64) NOT NULL, 
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    position geometry(POINT,4326) NOT NULL, 
    altitude_ft INTEGER NOT NULL, 
    speed_kt FLOAT NOT NULL, 
    heading_deg FLOAT NOT NULL, 
    source VARCHAR(50) NOT NULL, 
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(route_id) REFERENCES flight_routes (id)
);

CREATE INDEX idx_flight_observations_position ON flight_observations USING gist (position);

CREATE INDEX idx_flight_observations_position ON flight_observations USING gist (position);

CREATE INDEX ix_flight_observations_position ON flight_observations USING gist (position);

CREATE INDEX ix_flight_observations_route_id ON flight_observations (route_id);

CREATE INDEX ix_flight_observations_timestamp ON flight_observations (timestamp);

DROP INDEX idx_addrfeat_geom_gist;

DROP INDEX idx_addrfeat_tlid;

DROP INDEX idx_addrfeat_zipl;

DROP INDEX idx_addrfeat_zipr;

DROP TABLE addrfeat;

DROP TABLE loader_platform;

DROP TABLE loader_variables;

DROP INDEX idx_tiger_featnames_lname;

DROP INDEX idx_tiger_featnames_snd_name;

DROP INDEX idx_tiger_featnames_tlid_statefp;

DROP TABLE featnames;

DROP INDEX countysub_lookup_name_idx;

DROP INDEX countysub_lookup_state_idx;

DROP TABLE countysub_lookup;

DROP TABLE zip_lookup;

DROP TABLE zip_state;

DROP INDEX tige_cousub_the_geom_gist;

DROP TABLE cousub;

DROP INDEX idx_tiger_county;

DROP TABLE county;

DROP INDEX direction_lookup_abbrev_idx;

DROP TABLE direction_lookup;

DROP TABLE zip_state_loc;

DROP INDEX place_lookup_name_idx;

DROP INDEX place_lookup_state_idx;

DROP TABLE place_lookup;

DROP INDEX idx_edges_tlid;

DROP INDEX idx_tiger_edges_countyfp;

DROP INDEX idx_tiger_edges_the_geom_gist;

DROP TABLE edges;

DROP TABLE loader_lookuptables;

DROP TABLE zip_lookup_all;

DROP TABLE geocode_settings;

DROP INDEX tiger_place_the_geom_gist;

DROP TABLE place;

DROP TABLE topology;

DROP TABLE geocode_settings_default;

DROP TABLE tract;

DROP INDEX county_lookup_name_idx;

DROP INDEX county_lookup_state_idx;

DROP TABLE county_lookup;

DROP TABLE pagc_gaz;

DROP TABLE tabblock20;

DROP INDEX idx_tiger_addr_tlid_statefp;

DROP INDEX idx_tiger_addr_zip;

DROP TABLE addr;

DROP TABLE tabblock;

DROP INDEX idx_tiger_state_the_geom_gist;

DROP TABLE state;

DROP INDEX idx_tiger_faces_countyfp;

DROP INDEX idx_tiger_faces_tfid;

DROP INDEX tiger_faces_the_geom_gist;

DROP TABLE faces;

DROP TABLE zip_lookup_base;

DROP INDEX street_type_lookup_abbrev_idx;

DROP TABLE street_type_lookup;

DROP INDEX secondary_unit_lookup_abbrev_idx;

DROP TABLE secondary_unit_lookup;

DROP TABLE pagc_lex;

DROP TABLE layer;

DROP TABLE pagc_rules;

DROP TABLE spatial_ref_sys;

DROP TABLE state_lookup;

DROP TABLE zcta5;

DROP TABLE bg;

INSERT INTO alembic_version (version_num) VALUES ('897e3940acf9') RETURNING alembic_version.version_num;

COMMIT;

