// internal/storage/memory.go
package storage

import (
	"iot-go-gateway/internal/data"
	"sync"
)

const maxBufferSize = 100 // Store last 100 data points

type MemoryStore struct {
	mu       sync.RWMutex
	buffer   []*data.UniversalDataPoint
	capacity int
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		buffer:   make([]*data.UniversalDataPoint, 0, maxBufferSize),
		capacity: maxBufferSize,
	}
}

func (s *MemoryStore) Add(point *data.UniversalDataPoint) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if len(s.buffer) >= s.capacity {
		// Remove the oldest element
		s.buffer = s.buffer[1:]
	}
	s.buffer = append(s.buffer, point)
}

func (s *MemoryStore) GetRecent(count int) []*data.UniversalDataPoint {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if count <= 0 || count > len(s.buffer) {
		count = len(s.buffer)
	}
	// Return a copy to avoid race conditions if the caller modifies it
	result := make([]*data.UniversalDataPoint, count)
    copy(result, s.buffer[len(s.buffer)-count:])
	return result
}

func (s *MemoryStore) GetAll() []*data.UniversalDataPoint {
    s.mu.RLock()
    defer s.mu.RUnlock()
    result := make([]*data.UniversalDataPoint, len(s.buffer))
    copy(result, s.buffer)
    return result
}
