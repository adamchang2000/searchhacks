MAKEFILE_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
SERVER_DIR = $(MAKEFILE_DIR)/../../app/optimizer-server
SCHEMA = $(MAKEFILE_DIR)/schema.json
TYPES = $(MAKEFILE_DIR)/src/generated/api.ts

.PHONY: generate generate-schema generate-types clean

generate: generate-schema generate-types

generate-schema:
	cd $(SERVER_DIR) && uv run optimizer-manage -- export_openapi_schema --output $(SCHEMA) --indent 2

generate-types: $(SCHEMA)
	cd $(MAKEFILE_DIR) && npx openapi-typescript $(SCHEMA) -o $(TYPES)

clean:
	rm -f $(SCHEMA) $(TYPES)
