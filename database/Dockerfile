FROM postgres:16-alpine

COPY schema.sql /docker-entrypoint-initdb.d/001-schema.sql
COPY --chmod=755 init/002-import-seed.sh /docker-entrypoint-initdb.d/002-import-seed.sh
COPY seed /seed
