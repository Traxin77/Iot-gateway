// internal/data/models.go
package data

import "time"

// UniversalDataPoint - A common structure for incoming data
type UniversalDataPoint struct {
	Timestamp     time.Time              `json:"timestamp"`
	Source        string                 `json:"source,omitempty"` // e.g., "mqtt", "modbus", "coap", "websocket"
	DeviceID      string                 `json:"device_id,omitempty"` // Optional identifier
	Metrics       map[string]interface{} `json:"metrics"` // Flexible map for various sensor readings
	OriginalPayload []byte                `json:"-"` // Store raw payload if needed
}

// Alert - Structure for sending alerts
type Alert struct {
	Timestamp   time.Time `json:"timestamp"`
	Severity    string    `json:"severity"` // e.g., "WARN", "CRITICAL"
	Message     string    `json:"message"`
	Metric      string    `json:"metric"` // Which metric triggered the alert
	Value       float64   `json:"value"`  // The anomalous value
	DeviceID    string    `json:"device_id,omitempty"`
}
