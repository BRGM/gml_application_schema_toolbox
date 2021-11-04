SELECT count(*)
FROM information_schema.table_constraints
WHERE table_schema = '{schema}'
AND table_name = '{table}'
AND constraint_name = '{constraint}';
