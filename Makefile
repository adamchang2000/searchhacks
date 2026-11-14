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
# Every VM target acts on exactly one VM, chosen with a required HOST=<vm>.
VMS := optimizer driver
VM = searchhacks-$(HOST).exe.xyz
require_host = $(if $(and $(filter 1,$(words $(HOST))),$(filter $(VMS),$(HOST))),,$(error HOST is required and must be one of: $(VMS), e.g. make $@ HOST=optimizer))
require_unit = $(if $(UNIT),,$(error UNIT is required, e.g. make $@ HOST=optimizer UNIT=searchhacks-optimizer))

.PHONY: bootstrap deploy enable logs

# One-time (idempotent) setup of a VM: uv, node, clone, sync.
bootstrap:
	$(require_host)
	ssh $(VM) 'bash -s' < deploy/bootstrap.sh

# Pull latest main on a VM, sync deps, restart its enabled searchhacks-* services.
deploy:
	$(require_host)
	ssh $(VM) '~/searchhacks/deploy/update.sh'

# Enable + start a service on a VM.
enable:
	$(require_host)
	$(require_unit)
	ssh $(VM) 'sudo systemctl enable --now $(UNIT)'

# Tail a service's logs on a VM.
logs:
	$(require_host)
	$(require_unit)
	ssh $(VM) 'journalctl -u $(UNIT) -f -n 100'
