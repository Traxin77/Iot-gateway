// internal/data/parser.go
package data

import (
	"encoding/json"
	"log"
	"time"
)

// Parse tries to unmarshal raw data into UniversalDataPoint
func Parse(rawData []byte, source string) (*UniversalDataPoint, error) {
	var data UniversalDataPoint

	// First, try unmarshalling into a flexible map to inspect
	var genericPayload map[string]interface{}
	if err := json.Unmarshal(rawData, &genericPayload); err != nil {
		log.Printf("Error unmarshalling raw data: %v", err)
		return nil, err
	}

	// --- Adapt this logic based on your actual payload structures ---
	// Example: Try to extract common fields or handle specific known structures
	data.Timestamp = time.Now() // Default timestamp, try to overwrite if available in payload
	data.Source = source
	data.Metrics = make(map[string]interface{})
    data.OriginalPayload = rawData

	// Look for known keys (e.g., from Modbus script)
	if temp, ok := genericPayload["temperature"].(float64); ok {
		data.Metrics["temperature"] = temp
	}
	if hum, ok := genericPayload["humidity"].(float64); ok {
		data.Metrics["humidity"] = hum
	}
    // Look for device ID or other common fields
	if id, ok := genericPayload["sensor_id"].(string); ok {
        data.DeviceID = id
	} else if id, ok := genericPayload["device"].(string); ok {
        data.DeviceID = id
    }

	// If specific fields aren't found, maybe the whole payload is metrics?
    if len(data.Metrics) == 0 {
        // Be careful here - might need more checks
        data.Metrics = genericPayload
        // Potentially remove non-metric fields if necessary
        delete(data.Metrics, "timestamp") // Example
        delete(data.Metrics, "topic")     // Example
    }

    // Try to parse timestamp if present (adapt key and format)
    if tsStr, ok := genericPayload["timestamp"].(string); ok {
        // Add robust timestamp parsing here (e.g., multiple formats)
        if t, err := time.Parse(time.RFC3339Nano, tsStr); err == nil {
            data.Timestamp = t
        }
    }
	// --- End of adaptation section ---


	log.Printf("Parsed data: %+v", data)
	return &data, nil
}
