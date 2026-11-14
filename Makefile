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

# ---- Deployment (see README "Deployment") ----
HOSTS ?= searchhacks-optimizer.exe.xyz searchhacks-driver.exe.xyz

.PHONY: bootstrap deploy enable logs

# One-time (idempotent) setup of every VM: uv, node, clone, sync.
bootstrap:
	for h in $(HOSTS); do echo "== $$h"; ssh $$h 'bash -s' < deploy/bootstrap.sh || exit 1; done

# Pull latest main on every VM, sync deps, restart enabled searchhacks-* services.
deploy:
	for h in $(HOSTS); do echo "== $$h"; ssh $$h '~/searchhacks/deploy/update.sh' || exit 1; done

# Enable + start a service on one VM, e.g.  make enable HOST=optimizer UNIT=searchhacks-optimizer
enable:
	ssh searchhacks-$(HOST).exe.xyz 'sudo systemctl enable --now $(UNIT)'

# Tail a service's logs, e.g.  make logs HOST=optimizer UNIT=searchhacks-optimizer
logs:
	ssh searchhacks-$(HOST).exe.xyz 'journalctl -u $(UNIT) -f -n 100'
