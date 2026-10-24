# syntax=docker/dockerfile:1
#
# PeakPilot engine image for the Raspberry Pi 4 / 5 (64-bit Raspberry Pi OS, linux/arm64).
#
#   docker buildx build --platform linux/arm64 -t peakpilot:arm64 --load rust/peakpilot-core
#   docker run --rm peakpilot:arm64 run --scenario hot_evening --table
#
# The binary is linked statically against musl, so the runtime image is `scratch`: the
# binary and nothing else. Build on an arm64 host (Apple silicon, a Pi, or an Arm CI runner)
# to compile natively; on an x86 host Docker falls back to QEMU emulation, which is slower.
# Export just the binary with `--output type=local,dest=dist`.

FROM rust:1.99-alpine AS build
RUN apk add --no-cache musl-dev
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
# Cache the crate registry and build directory between builds; copy the binary out of the
# cache mount so it lands in the image layer.
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release --locked --bin peakpilot \
 && cp target/release/peakpilot /peakpilot

FROM scratch
LABEL org.opencontainers.image.title="peakpilot" \
      org.opencontainers.image.description="PeakPilot load-coordination engine (all device data SIMULATED)" \
      org.opencontainers.image.source="https://github.com/sohampatwardhan/PeakPilot" \
      org.opencontainers.image.licenses="MIT"
COPY --from=build /peakpilot /peakpilot
# Run as an unprivileged user; the engine needs no filesystem or network access.
USER 65534:65534
ENTRYPOINT ["/peakpilot"]
CMD ["list"]
