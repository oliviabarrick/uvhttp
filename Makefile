.PHONY: build
build:
	docker-compose -f docker/docker-compose.yml build

.PHONY: test
test: build
	docker-compose -f docker/docker-compose.yml up uvhttp
