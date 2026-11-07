# kavacha's launcher for thin apps (contract/api-1.md). make -C swift test | launcher | check-menu MENU=<menu.json>
ROOT := $(abspath ..)
MENU ?= $(ROOT)/contract/fixtures/leela/menu.json
BIN = $(shell swift build --package-path $(ROOT) -c release --arch arm64 --show-bin-path)
export MENU FILTER

.PHONY: test build launcher check-menu clean

# the shortcut tests build the menu bar of the Leela fixture, with no window on screen
test:
	KAVACHA_MENU_JSON="$$MENU" swift test --package-path $(ROOT) $(if $(value FILTER),--filter "$$FILTER")

build:
	swift build --package-path $(ROOT)

# the Tier A launcher, as a kavacha release carries it; prints its path and sha256
launcher:
	swift build --package-path $(ROOT) -c release --arch arm64 --product kavacha-launcher
	@shasum -a 256 "$(BIN)/kavacha-launcher"

check-menu: launcher
	"$(BIN)/kavacha-launcher" --check-menu "$$MENU"

clean:
	rm -rf $(ROOT)/.build
