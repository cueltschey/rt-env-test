from worker_thread import WorkerThread
import logging
import secrets
import sys
import os
from docker.types import DeviceRequest

class llm_worker(WorkerThread):
    def __init__(self, influxdb_client, docker_client, process_config):
        super().__init__(influxdb_client, docker_client, process_config)
        self.access_token = secrets.token_urlsafe(32)

    def start(self):
        self.config.image_name = "ghcr.io/cueltschey/rt-env-test"
        self.cleanup_old_containers()

        self.config.container_env = {
            "CONFIG": self.config.config_file,
        }
        self.setup_env()
        self.setup_networks()

        if not self.config.config_file is None:
            self.config.container_volumes[self.config.config_file] = {"bind": self.config.config_file, "mode": "ro"}
        self.setup_volumes()

        if self.config.process_config.get("enable_gpu", False):
            self.config.device_requests.append(
                DeviceRequest(
                    count=-1,
                    capabilities=[["gpu"]],
                    driver="nvidia"
                )
            )

        self.start_container()

    def get_token(self):
        return self.access_token
