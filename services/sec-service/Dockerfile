FROM golang:1.23-alpine AS builder
WORKDIR /app
RUN apk add --no-cache git
COPY go.mod ./
COPY . .
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /sec-service ./cmd/sec-service

FROM gcr.io/distroless/static-debian12
COPY --from=builder /sec-service /sec-service
EXPOSE 8080 9091
ENTRYPOINT ["/sec-service"]
