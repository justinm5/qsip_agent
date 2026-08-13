.PHONY: up down build tidy-go frontend test lint load-test replay research paper

up:
	docker compose up -d

down:
	docker compose down -v

build:
	docker compose build

tidy-go:
	cd services/sec-service && go mod tidy
	cd services/api-gateway && go mod tidy

frontend:
	cd frontend && npm install && npm run dev

train:
	docker compose exec feature-service python /app/scripts/train_model.py

research:
	docker compose exec feature-service python /app/scripts/generate_research_results.py

test:
	pytest tests -q

lint:
	ruff check python services tests scripts
	cd services/sec-service && go vet ./...
	cd services/api-gateway && go vet ./...

load-test:
	locust -f tests/locustfile.py --host http://localhost:8083

replay:
	curl -X POST http://localhost:8083/api/v1/replay \
		-H "Authorization: Bearer $$QSIP_TOKEN" \
		-H "Content-Type: application/json" \
		-d '{"source":"sec","event_type":"4","date_from":"2025-06-01T00:00:00","date_to":"2025-06-30T23:59:59","topic":"validated-events"}'

paper:
	curl http://localhost:8083/api/v1/paper/account \
		-H "Authorization: Bearer $$QSIP_TOKEN"
