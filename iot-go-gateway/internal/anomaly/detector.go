// internal/anomaly/detector.go
package anomaly

import (
	"fmt"
	"iot-go-gateway/internal/config"
	"iot-go-gateway/internal/data"
	"log"
)

type Detector struct {
	config *config.Config
}

func NewDetector(cfg *config.Config) *Detector {
	return &Detector{config: cfg}
}

// Check checks a data point for anomalies based on configured rules
func (d *Detector) Check(point *data.UniversalDataPoint) []data.Alert {
	var alerts []data.Alert

	rules := d.config.Anomaly.Rules // Get rules from loaded config

	for metricName, value := range point.Metrics {
		rule, ok := rules[metricName]
		if !ok {
			// No rule defined for this metric, skip
			continue
		}

		// Check if value is numeric (can be int or float)
		floatValue, numeric := value.(float64)
		if !numeric {
			// Try converting int to float64
			if intVal, ok := value.(int); ok {
				floatValue = float64(intVal)
				numeric = true
			} else if intVal, ok := value.(int64); ok { // JSON numbers can be decoded as int64
                floatValue = float64(intVal)
                numeric = true
            }
		}

		if !numeric {
			log.Printf("Skipping non-numeric metric for anomaly check: %s (%T)", metricName, value)
			continue
		}

		// Check against Min/Max thresholds
		if floatValue < rule.Min || floatValue > rule.Max {
			alert := data.Alert{
				Timestamp: point.Timestamp,
				Severity:  "WARN", // Could be dynamic
				Message:   fmt.Sprintf("Anomaly detected for %s: Value %.2f is outside range [%.2f, %.2f]", metricName, floatValue, rule.Min, rule.Max),
				Metric:    metricName,
				Value:     floatValue,
				DeviceID:  point.DeviceID,
			}
			alerts = append(alerts, alert)
			log.Printf("ALERT: %s", alert.Message)
		}
	}
	// --- Add more sophisticated checks here ---
	// e.g., Rate of change, standard deviation from moving average, etc.

	return alerts
}
