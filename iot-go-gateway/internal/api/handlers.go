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
}

func NewAPIHandler(store *storage.MemoryStore, detector *anomaly.Detector, hub *websocket.Hub, alerter *alerting.Alerter, webDir string) *APIHandler {
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
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// TODO: Determine source based on request path or header if needed
	source := "unknown" // Example: You might use different paths like /data/mqtt

	parsedData, err := data.Parse(body, source)
	if err != nil {
		log.Printf("Error parsing data: %v", err)
		http.Error(w, "Bad Request: Cannot parse JSON", http.StatusBadRequest)
		return
	}

	// 1. Store data (optional)
	h.store.Add(parsedData)

	// 2. Check for anomalies
	anomalies := h.detector.Check(parsedData)

	// 3. Process alerts if any anomalies found
	if len(anomalies) > 0 {
		h.alerter.ProcessAlerts(anomalies) // Alerter will broadcast via WebSocket Hub
	}

	// 4. Broadcast the received data via WebSocket
	h.hub.BroadcastData(parsedData)

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "received"})
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
