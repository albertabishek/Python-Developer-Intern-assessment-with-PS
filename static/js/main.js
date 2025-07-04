document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("demand-form");
    const destinationSelect = document.getElementById("destination-select");
    const loadingSpinner = document.getElementById("loading-spinner");
    const resultsContainer = document.getElementById("results-container");
    const errorMessage = document.getElementById("error-message");
    let airlineChart = null;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const destination = destinationSelect.value;
        if (!destination) {
            showError("Please select a destination city.");
            return;
        }

        showLoading(true);
        resultsContainer.classList.add("hidden");
        errorMessage.classList.add("hidden");

        try {
            const response = await fetch("/api/market-demand", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ destination: destination }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "An unknown error occurred.");
            }
            displayResults(data);
        } catch (error) {
            showError(error.message);
        } finally {
            showLoading(false);
        }
    });

    function showLoading(isLoading) {
        loadingSpinner.classList.toggle("hidden", !isLoading);
    }

    function showError(message) {
        errorMessage.textContent = `Error: ${message}`;
        errorMessage.classList.remove("hidden");
    }

    function displayResults(data) {
        document.getElementById("ai-summary-text").textContent = data.ai_summary;
        const popularRoutes = data.insights.popular_routes;
        const tableBody = document.querySelector("#routes-table tbody");
        tableBody.innerHTML = "";
        popularRoutes.forEach(route => {
            const row = `
                <tr>
                    <td>${route.airline}</td>
                    <td>${route.deal_count}</td>
                    <td>€${route.avg_price.toFixed(2)}</td>
                </tr>
            `;
            tableBody.innerHTML += row;
        });

        const chartCanvas = document.getElementById("airline-chart");
        const chartLabels = popularRoutes.map(r => r.airline);
        // Use deal_count for the popularity chart
        const chartData = popularRoutes.map(r => r.deal_count);
        if (airlineChart) {
            airlineChart.destroy();
        }
        airlineChart = new Chart(chartCanvas, {
            type: 'bar',
            data: {
                labels: chartLabels,
                datasets: [{
                    label: 'Number of Deals Found',
                    data: chartData,
                    backgroundColor: 'rgba(0, 123, 255, 0.6)',
                    borderColor: 'rgba(0, 123, 255, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true, title: { display: true, text: 'Number of Deals' } } },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Deals: ${context.parsed.y}`;
                            }
                        }
                    }
                }
            }
        });
        resultsContainer.classList.remove("hidden");
    }
});