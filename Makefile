.PHONY: build
build:
	docker-compose -f docker/docker-compose.yml build

.PHONY: test
test:
	docker-compose -f docker/docker-compose.yml up
