--
-- Table with one row that holds configurable values
--


DROP TABLE IF EXISTS configurables;
CREATE TABLE configurables (

    -- How far in advance we should schedule runs
    schedule_horizon    INTERVAL
			NOT NULL,

    -- How long we should keep old runs and tasks
    keep_runs_tasks	INTERVAL
			NOT NULL

);


-- This table gets exactly one row that can only ever be updated.
INSERT INTO configurables(
    schedule_horizon,
    keep_runs_tasks
)
VALUES (
    'P1D',     -- schedule_horizon
    'P7D'      -- keep_runs_tasks
)
;


CREATE OR REPLACE FUNCTION configurables_update()
RETURNS TRIGGER
AS $$
BEGIN
    NOTIFY configurables_changed;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER configurables_update
AFTER UPDATE
ON configurables
FOR EACH ROW
    EXECUTE PROCEDURE configurables_update();




CREATE OR REPLACE FUNCTION configurables_noalter()
RETURNS TRIGGER
AS $$
BEGIN
	RAISE EXCEPTION 'This table can only be updated.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER configurables_alter
BEFORE INSERT OR DELETE
ON configurables
FOR EACH ROW
    EXECUTE PROCEDURE configurables_noalter();

CREATE TRIGGER configurables_truncate
BEFORE TRUNCATE
ON configurables
EXECUTE PROCEDURE configurables_noalter();

