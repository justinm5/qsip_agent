FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /sec-service ./cmd/sec-service

FROM gcr.io/distroless/static-debian12
COPY --from=builder /sec-service /sec-service
EXPOSE 8080 9091
ENTRYPOINT ["/sec-service"]
