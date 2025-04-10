// internal/data/parser.go
package data

import (
	"encoding/json"
	"log"
	"time"
	"fmt"
	"iot-go-gateway/internal/config"
)

// Parse tries to unmarshal raw data into UniversalDataPoint
func Parse(rawData []byte, source string, cfg *config.Config) (*UniversalDataPoint, error) { // Pass config if needed for rules
	var genericPayload map[string]interface{}
	if err := json.Unmarshal(rawData, &genericPayload); err != nil {
		log.Printf("Error unmarshalling raw data for source %s: %v", source, err)
		return nil, fmt.Errorf("invalid JSON format: %w", err)
	}

	log.Printf("Received payload from source '%s': %+v", source, genericPayload)

	point := &UniversalDataPoint{
		Timestamp:     time.Now(), // Default, try to overwrite
		Source:        source,
		Metrics:       make(map[string]interface{}),
		OriginalPayload: rawData,
	}

	// --- Extract Common Fields ---
	if id, ok := genericPayload["device_id"].(string); ok {
		point.DeviceID = id
		delete(genericPayload, "device_id") // Remove from metrics map later
	} else if id, ok := genericPayload["sensor_id"].(string); ok {
		point.DeviceID = id // Use sensor_id as device_id if device_id not present
		delete(genericPayload, "sensor_id")
	}

	if tsVal, ok := genericPayload["timestamp"]; ok {
		parsedTime, err := parseTimestamp(tsVal)
		if err == nil {
			point.Timestamp = parsedTime
		} else {
			log.Printf("Warning: Could not parse timestamp from payload for source %s: %v", source, err)
		}
		delete(genericPayload, "timestamp")
	}

	// --- Process Remaining Fields as Metrics ---
	// Iterate through the map and assign recognized numeric types to metrics
	for key, value := range genericPayload {
		switch v := value.(type) {
		case float64:
			point.Metrics[key] = v
		case int:
			point.Metrics[key] = float64(v) // Convert int to float64
		case int64:
			point.Metrics[key] = float64(v) 
		case json.Number: 
			fVal, err := v.Float64()
			if err == nil {
				point.Metrics[key] = fVal
			} else {
				log.Printf("Warning: Could not convert json.Number '%s' to float64 for key '%s', source '%s'", v.String(), key, source)
				point.Metrics[key] = v.String() // Store as string if conversion fails
			}
        case string:
             point.Metrics[key] = v
        case bool:
             point.Metrics[key] = v
		default:
			log.Printf("Warning: Skipping metric '%s' with unhandled type %T for source '%s'", key, v, source)
		}
	}

    if len(point.Metrics) == 0 {
         log.Printf("Warning: No metrics extracted from payload for source '%s'. Original: %s", source, string(rawData))
    }


	log.Printf("Parsed data for source '%s': DeviceID=%s, Timestamp=%s, Metrics=%+v", source, point.DeviceID, point.Timestamp.Format(time.RFC3339), point.Metrics)
	return point, nil
}

// parseTimestamp tries various common formats
func parseTimestamp(ts interface{}) (time.Time, error) {
	switch v := ts.(type) {
	case string:
		// Try common string formats
		formats := []string{
			time.RFC3339Nano,
			time.RFC3339,
			"2006-01-02T15:04:05", // ISO 8601 without timezone
			"2006-01-02 15:04:05", // Common space format
		}
		for _, format := range formats {
			if t, err := time.Parse(format, v); err == nil {
				return t, nil
			}
		}
		return time.Time{}, fmt.Errorf("unrecognized string timestamp format: %s", v)
	case float64:
		// Assume Unix timestamp (seconds with optional milliseconds)
		sec := int64(v)
		nsec := int64((v - float64(sec)) * 1e9)
		return time.Unix(sec, nsec), nil
	case int:
		return time.Unix(int64(v), 0), nil // Assume Unix seconds
    case int64:
        return time.Unix(v, 0), nil // Assume Unix seconds
	case json.Number:
		
		fVal, err := v.Float64()
		if err == nil {
			sec := int64(fVal)
			nsec := int64((fVal - float64(sec)) * 1e9)
			return time.Unix(sec, nsec), nil
		}
        // Try parsing as int (Unix timestamp)
        iVal, err := v.Int64()
        if err == nil {
             return time.Unix(iVal, 0), nil
        }
		return time.Time{}, fmt.Errorf("unrecognized json.Number timestamp format: %s", v.String())
	default:
		return time.Time{}, fmt.Errorf("unsupported timestamp type: %T", v)
	}
}
