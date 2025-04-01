# Use Go base image
FROM golang:1.24-alpine

WORKDIR /app

# Copy module files and download dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source code and build
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o gateway ./cmd/gateway

# ✅ Fix: Directly copy web assets
COPY web /app/web

# Expose ports
EXPOSE 8080
EXPOSE 8081

# Run the application
CMD ["./gateway", "-config", ".", "-webdir", "./web"]

