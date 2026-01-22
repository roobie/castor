set windows-shell := ["pwsh.exe", "-NoLogo", "-NoProfile", "-Command"]

default:
	just --list

deps:
	cargo fetch
deps-update:
	cargo update
deps-upgrade:
	cargo install cargo-upgrade
	cargo-upgrade upgrade

fmt:
	cargo fmt --all

lint:
	cargo fmt --all -- --check
	cargo clippy --all -- -D warnings

build: deps lint
	cargo build

run BINARY *ARGS: build
	cargo run --release --bin {{BINARY}} -- {{ARGS}}

# Convenience wrappers for unified binary
run-castor *ARGS:
	just run castor {{ARGS}}

test: build
	cargo test

# Install all three binaries (unified + standalone for backward compatibility)
install: test
	cargo install --path ./castor

all: build test install
