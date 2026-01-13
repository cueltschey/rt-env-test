from worker_thread import WorkerThread
import logging
import secrets
import sys
import os

class RtTestComponent(WorkerThread):
    def __init__(self, influxdb_client, docker_client, process_config):
        super().__init__(influxdb_client, docker_client, process_config)
        self.access_token = secrets.token_urlsafe(32)

    def start(self):
        self.config.image_name = "ghcr.io/cueltschey/rt-env-test"
        self.cleanup_old_containers()

        self.config.container_env = {
            "CONFIG": "/test.yaml",
        }
        self.setup_env()
        self.setup_networks()

        self.config.container_volumes[self.config.config_file] = {"bind": "/test.yaml", "mode": "ro"}
        self.setup_volumes()

        self.start_container()

    def get_token(self):
        return self.access_token
