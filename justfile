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
	just -f ./casq-test/justfile fmt

lint:
	cargo fmt --all -- --check
	cargo clippy --all -- -D warnings
	just -f ./casq-test/justfile lint

lint-fix:
	cargo clippy --all --fix
	just -f ./casq-test/justfile lint-fix

build: deps lint
	cargo build

run BINARY *ARGS: build
	cargo run --release --bin {{BINARY}} -- {{ARGS}}

# Convenience wrappers for unified binary
run-casq *ARGS:
	just run casq {{ARGS}}

test: build
	cargo test
	just -f ./casq-test/justfile test

# Install all three binaries (unified + standalone for backward compatibility)
install: test
	cargo install --path ./casq

publish:
	# cargo login
	cargo publish --workspace

all: build test install

