.PHONY: build
build:
	docker-compose -f docker/docker-compose.yml build
	docker-compose -f docker/docker-compose.yml up build-docs

.PHONY: test
test: build
	docker-compose -f docker/docker-compose.yml up uvhttp
