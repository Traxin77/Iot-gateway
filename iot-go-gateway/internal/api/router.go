package api

import (
	"net/http"
	"path/filepath"
)

func SetupDataRouter(handler *APIHandler) *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/data", handler.HandleDataIngest) // Endpoint for Python scripts
	return mux
}

func SetupUIRouter(handler *APIHandler) *http.ServeMux {
	mux := http.NewServeMux()

	// Serve static files (CSS, JS)
	staticDir := http.Dir(filepath.Join(handler.webDir, "static"))
	fileServer := http.FileServer(staticDir)
	mux.Handle("/static/", http.StripPrefix("/static/", fileServer))

	// WebSocket endpoint
	mux.HandleFunc("/ws", handler.HandleWebSocket)

	// Serve the main HTML page
	mux.HandleFunc("/", handler.ServeWebUI)

	return mux
}
