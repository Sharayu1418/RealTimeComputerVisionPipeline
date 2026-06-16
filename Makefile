# Each service's Docker build context is its own folder, so common/ must be
# copied into each before building. `make up` does it for you.
SERVICES = ingest detector tracker api

sync-common:
	@for s in $(SERVICES); do rm -rf services/$$s/common && cp -r common services/$$s/common; done
	@echo "common/ synced into all services"

up: sync-common
	docker compose up --build -d
	@echo "dashboard:  http://localhost:8000"
	@echo "grafana:    http://localhost:3000"
	@echo "prometheus: http://localhost:9090"
	@echo "now run:    ./scripts/start_streams.sh"

down:
	docker compose down

logs:
	docker compose logs -f --tail=50

# the Phase-1 self-healing demo: kill the detector mid-run, watch it resume
chaos-detector:
	docker compose kill detector && sleep 5 && docker compose up -d detector
	@echo "detector killed and restarted — check the dashboard recovered and check Grafana for the gap"
