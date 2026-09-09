-- EDGE V1 recommendation immutability
CREATE RULE recommendations_no_update AS
ON UPDATE TO recommendations DO INSTEAD NOTHING;

CREATE RULE recommendations_no_delete AS
ON DELETE TO recommendations DO INSTEAD NOTHING;
