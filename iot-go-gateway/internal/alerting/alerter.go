// internal/alerting/alerter.go
package alerting

import (
	"iot-go-gateway/internal/data"
	"iot-go-gateway/internal/websocket" // Use websocket Hub
	"log"
)

type Alerter struct {
	hub *websocket.Hub
	// Add other notification channels here (e.g., email client, SMS service)
}

func NewAlerter(hub *websocket.Hub) *Alerter {
	return &Alerter{hub: hub}
}

// ProcessAlerts sends alerts via configured channels (currently WebSocket)
func (a *Alerter) ProcessAlerts(alerts []data.Alert) {
	if len(alerts) == 0 {
		return
	}

	log.Printf("Processing %d alerts", len(alerts))
	for _, alert := range alerts {
		// Send via WebSocket
		if a.hub != nil {
			a.hub.BroadcastAlert(alert)
		}

		// --- Add other notification logic here ---
		// e.g., sendEmail(alert), sendSMS(alert)
	}
}
