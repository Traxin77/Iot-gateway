package api

import (
	"net/http"
	"path/filepath"
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

func SetupDataRouter(apiHandler *APIHandler) *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	// --> Apply Authentication Middleware to /data endpoint <--
	r.Post("/data", apiHandler.Authenticate(apiHandler.HandleDataIngest))

	return r
}

func SetupUIRouter(apiHandler *APIHandler) *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	r.Get("/", apiHandler.ServeWebUI)
	r.Get("/ws", apiHandler.HandleWebSocket)

	// Serve static files (CSS, JS)
	staticPath := filepath.Join(apiHandler.webDir, "static")
	fs := http.FileServer(http.Dir(staticPath))
	r.Handle("/static/*", http.StripPrefix("/static/", fs))


	return r
}

