package api

import (
	"encoding/json"
	"html/template"
	"io"
	"iot-go-gateway/internal/alerting"
	"iot-go-gateway/internal/anomaly"
	"iot-go-gateway/internal/data"
	"iot-go-gateway/internal/storage"
	"iot-go-gateway/internal/websocket"
	"log"
	"time"
	"net/http"
	"path/filepath"
	"fmt"

	gwebsocket "github.com/gorilla/websocket" // Alias to avoid name conflict
)

var upgrader = gwebsocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true }, // Allow all origins for simplicity
}

type APIHandler struct {
	store    *storage.MemoryStore // Use an interface later for flexibility
	detector *anomaly.Detector
	hub      *websocket.Hub
	alerter  *alerting.Alerter
	tmpl     *template.Template
	webDir   string
	apiKey   string
}

func NewAPIHandler(store *storage.MemoryStore, detector *anomaly.Detector, hub *websocket.Hub, alerter *alerting.Alerter, webDir string, apiKey string) *APIHandler {
	// Load templates
    tmplPath := filepath.Join(webDir, "templates", "*.html")
	tmpl, err := template.ParseGlob(tmplPath)
	if err != nil {
		log.Fatalf("Error parsing templates: %v", err)
	}

	return &APIHandler{
		store:    store,
		detector: detector,
		hub:      hub,
		alerter:  alerter,
		tmpl:     tmpl,
		webDir:   webDir,
		apiKey:	  apiKey,
	}
}

func (h *APIHandler) Authenticate(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		providedKey := r.Header.Get("X-API-Key")
		if providedKey == "" {
			log.Println("Auth Error: Missing X-API-Key header")
			http.Error(w, "Forbidden: Missing API Key", http.StatusForbidden)
			return
		}
		if providedKey != h.apiKey {
			log.Printf("Auth Error: Invalid API Key provided: %s", providedKey)
			http.Error(w, "Forbidden: Invalid API Key", http.StatusForbidden)
			return
		}
		// If keys match, proceed to the next handler
		next(w, r)
	}
}

// HandleDataIngest receives data from the Python translators
func (h *APIHandler) HandleDataIngest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		log.Printf("Error reading request body: %v", err)
		http.Error(w, "Bad Request: Cannot read body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()
	source := r.URL.Query().Get("source")
	if source == "" {
		source = r.Header.Get("X-Source-Identifier") // Or check a header
	}
	if source == "" {
		source = "unknown" // Default if not specified
	}
	// --- End Determine Source ---


	// Pass nil for config if parser doesn't use it, or pass h.detector.config if needed
	parsedData, err := data.Parse(body, source, nil)
	if err != nil {
		log.Printf("Error parsing data from source '%s': %v", source, err)
		// Provide more specific error message if possible
		errMsg := fmt.Sprintf("Bad Request: Cannot parse payload. Error: %v", err)
		http.Error(w, errMsg, http.StatusBadRequest)
		return
	}

    // Ensure DeviceID is populated if possible (e.g. from source-specific logic if not in payload)
    if parsedData.DeviceID == "" {
         parsedData.DeviceID = fmt.Sprintf("device_from_%s", source) // Example default
    }

	// 1. Store data (optional)
	h.store.Add(parsedData)

	// 2. Check for anomalies
    // Pass config explicitly if needed, or detector holds it
	anomalies := h.detector.Check(parsedData)

	// 3. Process alerts if any anomalies found
	if len(anomalies) > 0 {
		h.alerter.ProcessAlerts(anomalies) // Alerter will broadcast via WebSocket Hub
	}

	// 4. Broadcast the received data via WebSocket
	h.hub.BroadcastData(parsedData)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "received", "source": source})
}
// HandleWebSocket upgrades connections and registers clients with the hub
func (h *APIHandler) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}

	client := &websocket.Client{Hub: h.hub, Conn: conn, Send: make(chan []byte, 256)}
	client.Hub.RegisterClient(client)

	// Start read/write pumps in separate goroutines
	go client.WritePump()
	go client.ReadPump() // Must run ReadPump to handle control messages (close, pong)

    log.Printf("WebSocket connection established: %s", conn.RemoteAddr())

    // Send recent data upon connection
    go h.sendInitialData(client)
}

// ServeWebUI serves the main HTML page
func (h *APIHandler) ServeWebUI(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	// initialData := h.store.GetRecent(50) // Get some recent data
	err := h.tmpl.ExecuteTemplate(w, "index.html", nil) // Pass initialData if needed by template
	if err != nil {
		log.Printf("Error executing template: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
	}
}

// sendInitialData sends recent history to a newly connected client
func (h *APIHandler) sendInitialData(client *websocket.Client) {
    recentData := h.store.GetAll() // Or GetRecent(N)
    if len(recentData) == 0 {
        return
    }

    // Wrap in the standard message format
    messageBytes, err := json.Marshal(map[string]interface{}{
        "type": "history",
        "payload": recentData,
    })
    if err != nil {
        log.Printf("Error marshalling history data: %v", err)
        return
    }

    // Send safely through the client's channel
    select {
    case client.Send <- messageBytes:
        log.Printf("Sent history data to client %s", client.Conn.RemoteAddr())
    case <-time.After(5 * time.Second): // Timeout if client channel is blocked
        log.Printf("Timeout sending history data to client %s", client.Conn.RemoteAddr())
    }
}
