<script>
document.addEventListener('DOMContentLoaded', function() {
   const ctx = document.getElementById('chart-canvas');
    if (ctx) {
        // Convert Jinja variables into numbers safely
        const pending = Number({{ total_pending | default(0) | int }});
        const hired = Number({{ total_hired | default(0) | int }});
        const rejected = Number({{ total_rejected | default(0) | int }});

        new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: ['Pending', 'Hired', 'Rejected'],
                datasets: [{
                    label: 'Applicant Status',
                    data: [pending, hired, rejected],
                    backgroundColor: [
                        'rgba(65, 105, 225, 0.8)',  // Blue
                        'rgba(40, 167, 69, 0.8)',   // Green
                        'rgba(220, 53, 69, 0.8)'    // Red
                    ],
                    borderColor: [
                        'rgba(65, 105, 225, 1)',
                        'rgba(40, 167, 69, 1)',
                        'rgba(220, 53, 69, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0 // Only integers on y-axis
                        }
                    }
                }
            }
        });
    }
});

</script>
