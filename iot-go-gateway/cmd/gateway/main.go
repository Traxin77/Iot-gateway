// cmd/gateway/main.go
package main

import (
	"crypto/tls"
	"flag"
	"fmt"
	"iot-go-gateway/internal/alerting"
	"iot-go-gateway/internal/anomaly"
	"iot-go-gateway/internal/api"
	"iot-go-gateway/internal/config"
	"iot-go-gateway/internal/storage"
	"iot-go-gateway/internal/websocket"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	// --- Configuration ---
	configPath := flag.String("config", ".", "Path to the configuration file directory")
	webDir := flag.String("webdir", "./web", "Path to the web assets directory")
	certFile := flag.String("cert", "certs/server.crt", "Path to TLS certificate file")
	keyFile := flag.String("key", "certs/server.key", "Path to TLS key file")
	flag.Parse()

	err := config.LoadConfig(*configPath)
	if err != nil {
		log.Printf("Error loading config, continuing with defaults: %v", err)
		// Application might still run with defaults set in config.LoadConfig
	}
	cfg := &config.AppConfig // Use the loaded config
	apiKey := os.Getenv("GATEWAY_API_KEY")
	if apiKey == "" {
		log.Fatal("GATEWAY_API_KEY environment variable not set")
	}
	// --- Initialize Components ---
	store := storage.NewMemoryStore()
	hub := websocket.NewHub()
	detector := anomaly.NewDetector(cfg)
	alerter := alerting.NewAlerter(hub) // Pass hub to alerter

	apiHandler := api.NewAPIHandler(store, detector, hub, alerter, *webDir, apiKey)

	// --- Start WebSocket Hub ---
	go hub.Run()

	// --- Setup HTTP Servers ---
	dataRouter := api.SetupDataRouter(apiHandler)
	uiRouter := api.SetupUIRouter(apiHandler)

	tlsConfig := &tls.Config{
		MinVersion: tls.VersionTLS12,
	}

	dataServer := &http.Server{
		Addr:      fmt.Sprintf(":%d", cfg.Server.DataPort),
		Handler:   dataRouter,
		TLSConfig: tlsConfig,
	}
	uiServer := &http.Server{
		Addr:      fmt.Sprintf(":%d", cfg.Server.UIPort),
		Handler:   uiRouter,
		TLSConfig: tlsConfig,
	}

	// --- Start Servers in Goroutines ---
	go func() {
		log.Printf("Starting Data Ingestion Server (HTTPS) on port %d", cfg.Server.DataPort)
		// --> Use ListenAndServeTLS <--
		if err := dataServer.ListenAndServeTLS(*certFile, *keyFile); err != http.ErrServerClosed {
			log.Fatalf("Data Server ListenAndServeTLS error: %v", err)
		}
	}()

	go func() {
		log.Printf("Starting Web UI & WebSocket Server (HTTPS/WSS) on port %d", cfg.Server.UIPort)
		// --> Use ListenAndServeTLS <--
		if err := uiServer.ListenAndServeTLS(*certFile, *keyFile); err != http.ErrServerClosed {
			log.Fatalf("UI Server ListenAndServeTLS error: %v", err)
		}
	}()

	// --- Graceful Shutdown ---
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down servers...")

	// Add shutdown logic for servers (e.g., dataServer.Shutdown(context.Background()))
	// Close hub, database connections etc.

	log.Println("Servers gracefully stopped.")
}
