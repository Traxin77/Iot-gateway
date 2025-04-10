// internal/auth/auth.go
package auth

import (
	"crypto/subtle"
	"errors"
	"fmt"
	"github.com/dgrijalva/jwt-go"
	"golang.org/x/crypto/bcrypt"
	"net/http"
	"strings"
	"time"
	"context"
)

// Config holds authentication configuration
type Config struct {
	JWTSecret       string   `mapstructure:"jwt_secret"`
	JWTExpiration   int      `mapstructure:"jwt_expiration"` // in minutes
	APIKeys         []string `mapstructure:"api_keys"`
	AllowedUsers    []User   `mapstructure:"users"`
	EnableClientCerts bool   `mapstructure:"enable_client_certs"`
}

type User struct {
	Username     string `mapstructure:"username"`
	PasswordHash string `mapstructure:"password_hash"`
	Role         string `mapstructure:"role"`
}

// AuthManager handles authentication and authorization
type AuthManager struct {
	config Config
}

// Claims represents JWT claims
type Claims struct {
	Username string `json:"username"`
	Role     string `json:"role"`
	jwt.StandardClaims
}

// NewAuthManager creates a new authentication manager
func NewAuthManager(config Config) *AuthManager {
	return &AuthManager{
		config: config,
	}
}

// GenerateJWT creates a new JWT token for a user
func (am *AuthManager) GenerateJWT(username, role string) (string, error) {
	expirationTime := time.Now().Add(time.Duration(am.config.JWTExpiration) * time.Minute)
	
	claims := &Claims{
		Username: username,
		Role:     role,
		StandardClaims: jwt.StandardClaims{
			ExpiresAt: expirationTime.Unix(),
			IssuedAt:  time.Now().Unix(),
			Issuer:    "iot-gateway",
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(am.config.JWTSecret))
	
	if err != nil {
		return "", err
	}
	
	return tokenString, nil
}

// ValidateJWT validates the JWT token
func (am *AuthManager) ValidateJWT(tokenString string) (*Claims, error) {
	claims := &Claims{}
	
	token, err := jwt.ParseWithClaims(tokenString, claims, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(am.config.JWTSecret), nil
	})
	
	if err != nil {
		return nil, err
	}
	
	if !token.Valid {
		return nil, errors.New("invalid token")
	}
	
	return claims, nil
}

// ValidateAPIKey checks if the provided API key is valid
func (am *AuthManager) ValidateAPIKey(apiKey string) bool {
	for _, validKey := range am.config.APIKeys {
		if subtle.ConstantTimeCompare([]byte(apiKey), []byte(validKey)) == 1 {
			return true
		}
	}
	return false
}

// AuthenticateUser validates username and password
func (am *AuthManager) AuthenticateUser(username, password string) (bool, string, error) {
	for _, user := range am.config.AllowedUsers {
		if user.Username == username {
			err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password))
			if err == nil {
				return true, user.Role, nil
			}
			return false, "", errors.New("invalid password")
		}
	}
	return false, "", errors.New("user not found")
}

// HashPassword creates a bcrypt hash from a password
func HashPassword(password string) (string, error) {
	bytes, err := bcrypt.GenerateFromPassword([]byte(password), 14)
	return string(bytes), err
}

// Middleware for API authentication
func (am *AuthManager) JWTMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		
		if authHeader == "" {
			http.Error(w, "Authorization header required", http.StatusUnauthorized)
			return
		}
		
		bearerToken := strings.Split(authHeader, " ")
		if len(bearerToken) != 2 || bearerToken[0] != "Bearer" {
			http.Error(w, "Invalid authorization format", http.StatusUnauthorized)
			return
		}
		
		claims, err := am.ValidateJWT(bearerToken[1])
		if err != nil {
			http.Error(w, "Invalid or expired token", http.StatusUnauthorized)
			return
		}
		
		// Add claims to request context
		ctx := r.Context()
		ctx = context.WithValue(ctx, "username", claims.Username)
		ctx = context.WithValue(ctx, "role", claims.Role)
		
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// Middleware for API key authentication
func (am *AuthManager) APIKeyMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		apiKey := r.Header.Get("X-API-Key")
		
		if apiKey == "" {
			http.Error(w, "API key required", http.StatusUnauthorized)
			return
		}
		
		if !am.ValidateAPIKey(apiKey) {
			http.Error(w, "Invalid API key", http.StatusUnauthorized)
			return
		}
		
		next.ServeHTTP(w, r)
	})
}

