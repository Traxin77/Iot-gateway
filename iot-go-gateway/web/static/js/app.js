document.addEventListener('DOMContentLoaded', (event) => {
    const connectionStatus = document.getElementById('connection-status');
    const alertsList = document.getElementById('alerts-list');
    const dataList = document.getElementById('realtime-data-list');
    const ctx = document.getElementById('dataChart').getContext('2d');

    const MAX_DATA_POINTS = 50; // Max points to show on chart & list
    const MAX_ALERTS = 20; // Max alerts to show in list

    let dataChart;
    let socket;

    function initializeChart() {
        dataChart = new Chart(ctx, {
            type: 'line',
            data: {
                // labels: [], // Handled by time scale adapter
                datasets: [
                    {
                        label: 'Temperature (°C)',
                        data: [], // {x: timestamp, y: value}
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.5)',
                        yAxisID: 'y',
                    },
                    {
                        label: 'Humidity (%)',
                        data: [], // {x: timestamp, y: value}
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        yAxisID: 'y1', // Use a secondary axis if scales differ significantly
                    }
                    // Add more datasets here if needed for other metrics
                ]
            },
            options: {
                 responsive: true,
                 maintainAspectRatio: false,
                 scales: {
                    x: {
                        type: 'time', // Use time scale
                        time: {
                             unit: 'second', // Adjust based on data frequency
                             tooltipFormat: 'YYYY-MM-DD HH:mm:ss',
                             displayFormats: {
                                 second: 'HH:mm:ss',
                                 minute: 'HH:mm',
                                 hour: 'HH:mm'
                             }
                        },
                        title: {
                            display: true,
                            text: 'Timestamp'
                        }
                    },
                    y: { // Primary Y-axis (e.g., Temperature)
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                           display: true,
                           text: 'Temperature (°C)'
                        }
                    },
                    y1: { // Secondary Y-axis (e.g., Humidity)
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Humidity (%)'
                        },
                         // Ensure grid lines don't overlap excessively
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                },
                plugins: {
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                    },
                    legend: {
                        position: 'top',
                    }
                },
                // Optimization: disable animations for performance with real-time data
                 animation: false,
                 parsing: false // Data is already in {x, y} format
            }
        });
    }

    function connectWebSocket() {
        // Adjust protocol (ws/wss) and host/port as needed
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws`; // Assumes UI & WS on same host/port

        console.log(`Attempting to connect to WebSocket: ${wsUrl}`);
        socket = new WebSocket(wsUrl);

        socket.onopen = function(event) {
            console.log('WebSocket connection established');
            connectionStatus.textContent = 'Status: Connected';
            connectionStatus.className = 'connected';
        };

        socket.onmessage = function(event) {
            // console.log('Message from server:', event.data);
            try {
                const message = JSON.parse(event.data);
                handleMessage(message);
            } catch (e) {
                console.error('Error parsing message:', e);
            }
        };

        socket.onclose = function(event) {
            console.log('WebSocket connection closed:', event);
            connectionStatus.textContent = 'Status: Disconnected. Retrying...';
            connectionStatus.className = 'disconnected';
            // Attempt to reconnect after a delay
            setTimeout(connectWebSocket, 5000); // Retry every 5 seconds
        };

        socket.onerror = function(error) {
            console.error('WebSocket error:', error);
            connectionStatus.textContent = 'Status: Error';
            connectionStatus.className = 'disconnected';
            // Consider adding retry logic here too, or rely on onclose
        };
    }

    function handleMessage(message) {
        if (!message.type || !message.payload) {
            console.warn("Received malformed message:", message);
            return;
        }

        switch (message.type) {
            case 'data':
                addDataPoint(message.payload);
                displayRawData(message.payload);
                break;
            case 'alert':
                displayAlert(message.payload);
                break;
            case 'history':
                 if (Array.isArray(message.payload)) {
                    console.log(`Received history with ${message.payload.length} points.`);
                    loadHistory(message.payload);
                 }
                 break;
            default:
                console.warn("Unknown message type:", message.type);
        }
    }

    function loadHistory(historyData) {
        // Clear existing chart data and lists
        dataChart.data.datasets.forEach(dataset => dataset.data = []);
        dataList.innerHTML = ''; // Clear raw data list

        // Populate with history
        historyData.forEach(point => {
            addDataPoint(point, false); // Add without immediate update
            displayRawData(point, false); // Add without immediate update
        });

        dataChart.update(); // Update chart once after loading history
        checkListLimits(); // Clean up lists if history exceeds limits
    }


    function addDataPoint(point, updateChart = true) {
        if (!point.metrics || !point.timestamp) {
            console.warn("Data point missing metrics or timestamp:", point);
            return;
        }

        const timestamp = new Date(point.timestamp); // Parse timestamp string

        // Update specific datasets based on metrics found
        if (point.metrics.temperature !== undefined) {
            const tempData = dataChart.data.datasets[0].data;
            tempData.push({ x: timestamp.valueOf(), y: point.metrics.temperature });
            if (tempData.length > MAX_DATA_POINTS) {
                tempData.shift(); // Remove oldest point
            }
        }

        if (point.metrics.humidity !== undefined) {
            const humData = dataChart.data.datasets[1].data;
            humData.push({ x: timestamp.valueOf(), y: point.metrics.humidity });
            if (humData.length > MAX_DATA_POINTS) {
                humData.shift(); // Remove oldest point
            }
        }

        // --- Add logic for other metrics/datasets here ---

        if (updateChart) {
             dataChart.update(); // Update the chart visually
        }
    }

    function displayRawData(point, updateList = true) {
        const listItem = document.createElement('li');
        const timestamp = new Date(point.timestamp).toLocaleString();
        let metricsString = Object.entries(point.metrics)
                                  .map(([key, value]) => `${key}: ${value}`)
                                  .join(', ');
        listItem.textContent = `[${timestamp}] Source: ${point.source || 'N/A'}, Device: ${point.device_id || 'N/A'} | Metrics: { ${metricsString} }`;
        listItem.setAttribute('data-timestamp', new Date(point.timestamp).toISOString()); // For sorting/filtering if needed

        // Add to the top of the list
        dataList.insertBefore(listItem, dataList.firstChild);

        // Remove placeholder if present
        const placeholder = dataList.querySelector('li:only-child');
        if (placeholder && placeholder.textContent === 'Waiting for data...') {
            dataList.removeChild(placeholder);
        }

         if(updateList) {
            checkListLimits();
        }
    }


    function displayAlert(alert) {
        const listItem = document.createElement('li');
        const timestamp = new Date(alert.timestamp).toLocaleString();
        listItem.textContent = `[${timestamp}] ${alert.severity || 'ALERT'}: ${alert.message}`;
        listItem.classList.add(alert.severity ? alert.severity.toLowerCase() : 'warn'); // Add class for styling

        // Add to the top of the list
        alertsList.insertBefore(listItem, alertsList.firstChild);

         // Remove placeholder if present
        const placeholder = alertsList.querySelector('li:only-child');
        if (placeholder && placeholder.textContent === 'No alerts yet.') {
            alertsList.removeChild(placeholder);
        }

        checkListLimits();
    }

     function checkListLimits() {
        // Limit displayed alerts
        while (alertsList.children.length > MAX_ALERTS) {
            alertsList.removeChild(alertsList.lastChild);
        }
        // Limit displayed raw data points
        while (dataList.children.length > MAX_DATA_POINTS) {
            dataList.removeChild(dataList.lastChild);
        }
    }


    // --- Initialization ---
    initializeChart();
    connectWebSocket();
});
