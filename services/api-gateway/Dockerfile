FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /api-gateway ./cmd/api-gateway

FROM gcr.io/distroless/static-debian12
COPY --from=builder /api-gateway /api-gateway
EXPOSE 8083 8084
ENTRYPOINT ["/api-gateway"]
