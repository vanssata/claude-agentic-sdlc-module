.PHONY: test qa up

COMPOSE = docker compose

up: ## Start the containers
	$(COMPOSE) up -d

# Static analysis and coding standard
qa:
	vendor/bin/phpstan analyse

test: qa ## The fast suite, e2e excluded
	vendor/bin/phpunit --exclude-group e2e
