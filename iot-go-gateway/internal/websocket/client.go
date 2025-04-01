// internal/websocket/client.go (Add this file)
package websocket

import (
	"log"
	"time"

	"github.com/gorilla/websocket"
)

const (
	writeWait      = 10 * time.Second    // Time allowed to write a message to the peer.
	pongWait       = 60 * time.Second    // Time allowed to read the next pong message from the peer.
	pingPeriod     = (pongWait * 9) / 10 // Send pings to peer with this period. Must be less than pongWait.
	maxMessageSize = 512                 // Maximum message size allowed from peer.
)

// Client is a middleman between the websocket connection and the hub.
type Client struct {
	Hub  *Hub
	Conn *websocket.Conn    // The websocket connection.
	Send chan []byte        // Buffered channel of outbound messages.
}

// readPump pumps messages from the websocket connection to the hub.
func (c *Client) ReadPump() {
	defer func() {
		c.Hub.unregister <- c
		c.Conn.Close()
		log.Printf("WebSocket readPump finished for %s", c.Conn.RemoteAddr())
	}()
	c.Conn.SetReadLimit(maxMessageSize)
	c.Conn.SetReadDeadline(time.Now().Add(pongWait))
	c.Conn.SetPongHandler(func(string) error { c.Conn.SetReadDeadline(time.Now().Add(pongWait)); return nil })
	for {
        // Gateway primarily broadcasts; reading from client might not be needed
        // unless you want control messages from UI (e.g., request history)
		_, message, err := c.Conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("WebSocket read error: %v", err)
			}
			break
		}
        // Process message if needed, otherwise ignore
		log.Printf("Received message from client %s: %s", c.Conn.RemoteAddr(), message)
	}
}

// writePump pumps messages from the hub to the websocket connection.
func (c *Client) WritePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.Conn.Close()
		log.Printf("WebSocket writePump finished for %s", c.Conn.RemoteAddr())
	}()
	for {
		select {
		case message, ok := <-c.Send:
			c.Conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				// The hub closed the channel.
				c.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := c.Conn.NextWriter(websocket.TextMessage)
			if err != nil {
				log.Printf("WebSocket writer error: %v", err)
				return
			}
			w.Write(message)

			// Add queued messages to the current websocket message.
            // Improves efficiency by batching writes.
			n := len(c.Send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'}) // Optional: Add newline separator if needed
				w.Write(<-c.Send)
			}

			if err := w.Close(); err != nil {
				log.Printf("WebSocket writer close error: %v", err)
				return
			}
		case <-ticker.C:
			c.Conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.Conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				log.Printf("WebSocket ping error: %v", err)
				return
			}
		}
	}
}
