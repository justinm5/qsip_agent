"""Load test for API gateway."""

from locust import HttpUser, task


class QSIPUser(HttpUser):
    @task
    def get_signals(self):
        self.client.get("/api/v1/signals?limit=100", headers={"Authorization": "Bearer test-token"})

    @task
    def get_market(self):
        self.client.get("/api/v1/market/AAPL", headers={"Authorization": "Bearer test-token"})
