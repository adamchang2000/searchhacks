.PHONY: all install generate-api typecheck server ui mock-driver migrate

all: generate-api

install:
	cd app/optimizer-server && uv sync
	npm install

# Export the OpenAPI schema from the optimizer server and regenerate TS types.
generate-api:
	$(MAKE) -C lib/optimizer-protocol generate

typecheck:
	npm run typecheck

migrate:
	cd app/optimizer-server && uv run optimizer-manage --config config/dev.json -- migrate

server:
	cd app/optimizer-server && uv run optimizer-server --config config/dev.json --auto-reload

ui:
	npm run dev -w @searchhacks/optimizer-ui

mock-driver:
	npm start -w @searchhacks/mock-driver -- $(ARGS)
