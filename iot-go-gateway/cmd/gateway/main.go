// cmd/gateway/main.go
package main

import (
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
    "flag"
)

func main() {
    // --- Configuration ---
    configPath := flag.String("config", ".", "Path to the configuration file directory")
    webDir := flag.String("webdir", "./web", "Path to the web assets directory")
    flag.Parse()

	err := config.LoadConfig(*configPath)
	if err != nil {
        log.Printf("Error loading config, continuing with defaults: %v", err)
		// Application might still run with defaults set in config.LoadConfig
	}
	cfg := &config.AppConfig // Use the loaded config

	// --- Initialize Components ---
	store := storage.NewMemoryStore()
	hub := websocket.NewHub()
	detector := anomaly.NewDetector(cfg)
	alerter := alerting.NewAlerter(hub) // Pass hub to alerter

	apiHandler := api.NewAPIHandler(store, detector, hub, alerter, *webDir)

	// --- Start WebSocket Hub ---
	go hub.Run()

	// --- Setup HTTP Servers ---
	dataRouter := api.SetupDataRouter(apiHandler)
	uiRouter := api.SetupUIRouter(apiHandler)

	dataServer := &http.Server{
		Addr:    fmt.Sprintf(":%d", cfg.Server.DataPort),
		Handler: dataRouter,
	}
	uiServer := &http.Server{
		Addr:    fmt.Sprintf(":%d", cfg.Server.UIPort),
		Handler: uiRouter,
	}

	// --- Start Servers in Goroutines ---
	go func() {
		log.Printf("Starting Data Ingestion Server on port %d", cfg.Server.DataPort)
		if err := dataServer.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("Data Server ListenAndServe error: %v", err)
		}
	}()

	go func() {
		log.Printf("Starting Web UI & WebSocket Server on port %d", cfg.Server.UIPort)
		if err := uiServer.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("UI Server ListenAndServe error: %v", err)
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
