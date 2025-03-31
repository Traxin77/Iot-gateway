// internal/config/config.go
package config

import (
	"github.com/spf13/viper" // Example using viper
	"log"
)

type Config struct {
	Server struct {
		DataPort int `mapstructure:"data_port"`
		UIPort   int `mapstructure:"ui_port"`
	} `mapstructure:"server"`
	Anomaly struct {
		Rules map[string]Rule `mapstructure:"rules"`
	} `mapstructure:"anomaly"`
	// Add other config sections
}

type Rule struct {
	Min float64 `mapstructure:"min"`
	Max float64 `mapstructure:"max"`
}

var AppConfig Config

func LoadConfig(path string) error {
	viper.SetConfigName("config") // name of config file (without extension)
	viper.SetConfigType("yaml")   // or json, toml
	viper.AddConfigPath(path)     // path to look for the config file in
	viper.AutomaticEnv()          // read in environment variables that match

	if err := viper.ReadInConfig(); err != nil {
		log.Printf("Warning: Error reading config file: %s\n", err)
        // Set defaults if file not found or partially missing
        setDefaults()
	}

	err := viper.Unmarshal(&AppConfig)
	if err != nil {
		log.Fatalf("Unable to decode into struct: %v", err)
        return err
	}

    log.Printf("Configuration loaded: %+v", AppConfig)
    return nil
}

func setDefaults() {
    viper.SetDefault("server.data_port", 8080)
    viper.SetDefault("server.ui_port", 8081)
    // Set other defaults as needed
}
