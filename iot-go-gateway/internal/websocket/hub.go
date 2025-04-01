// internal/websocket/hub.go
package websocket

import (
	"encoding/json"
	"log"
	"sync"
)

// Hub maintains the set of active clients and broadcasts messages.
type Hub struct {
	clients    map[*Client]bool
	broadcast  chan []byte // Channel for messages to broadcast
	register   chan *Client // Channel for registering clients
	unregister chan *Client // Channel for unregistering clients
	mu         sync.RWMutex
}

func NewHub() *Hub {
	return &Hub{
		broadcast:  make(chan []byte),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		clients:    make(map[*Client]bool),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			log.Printf("WebSocket client registered: %s", client.Conn.RemoteAddr())
			h.mu.Unlock()
            // Optionally send initial data (e.g., recent history)
            // h.sendInitialData(client)

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.Send)
				log.Printf("WebSocket client unregistered: %s", client.Conn.RemoteAddr())
			}
			h.mu.Unlock()

		case message := <-h.broadcast:
			h.mu.RLock()
			// log.Printf("Broadcasting message to %d clients", len(h.clients))
			for client := range h.clients {
				select {
				case client.Send <- message:
				default:
					// Assume client is blocked or gone, unregister
					log.Printf("WebSocket client %s send buffer full or closed, removing.", client.Conn.RemoteAddr())
					close(client.Send)
					delete(h.clients, client) 
				}
			}
			h.mu.RUnlock()
		}
	}
}
// RegisterClient safely registers a new client to the hub
func (h *Hub) RegisterClient(client *Client) {
    h.register <- client
}

// BroadcastData sends data (like UniversalDataPoint) to all clients
func (h *Hub) BroadcastData(data interface{}) {
	messageBytes, err := json.Marshal(map[string]interface{}{"type": "data", "payload": data})
	if err != nil {
		log.Printf("Error marshalling data for broadcast: %v", err)
		return
	}
	h.broadcast <- messageBytes
}

// BroadcastAlert sends an alert message to all clients
func (h *Hub) BroadcastAlert(alert interface{}) {
	messageBytes, err := json.Marshal(map[string]interface{}{"type": "alert", "payload": alert})
	if err != nil {
		log.Printf("Error marshalling alert for broadcast: %v", err)
		return
	}
	h.broadcast <- messageBytes
}

// --- Client struct and read/write pump logic needed here ---
// See gorilla/websocket chat example for Client struct and read/write goroutines
// internal/websocket/client.go would contain this
