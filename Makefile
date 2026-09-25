SHELL := /bin/bash
.DEFAULT_GOAL := aide
export PHAROS_UID := $(shell id -u)
export PHAROS_GID := $(shell id -g)
export MITMPROXY_VERSION ?= 12.2.3
DC := docker compose -f compose.yaml $(foreach f,$(sort $(wildcard compose/*.yaml)),-f $(f))

include $(sort $(wildcard mk/*.mk))

aide: ## Affiche les cibles disponibles
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk -F':.*## ' '{printf "  %-22s %s\n", $$1, $$2}'
.PHONY: aide
