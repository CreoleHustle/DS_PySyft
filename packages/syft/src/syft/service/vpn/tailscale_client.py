# stdlib
from enum import Enum
import json
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Type
from typing import Union

# relative
from ...client.connection import NodeConnection
from ...serde.serializable import serializable
from ...types.syft_object import SYFT_OBJECT_VERSION_1
from ...types.syft_object import SyftObject
from ..response import SyftError
from ..response import SyftSuccess
from .headscale_client import BaseVPNClient
from .headscale_client import VPNRoutes


class TailscaleRoutes(VPNRoutes):
    SERVER_UP = "/commands/up"
    SERVER_DOWN = "/commands/down"
    SERVER_STATUS = "/commands/status"


class ConnectionType(Enum):
    RELAY = "relay"
    DIRECT = "direct"


class ConnectionStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"


class TailScaleState(Enum):
    RUNNING = "Running"
    STOPPED = "Stopped"


class TailscalePeer(SyftObject):
    __canonical_name__ = "TailscalePeer"
    __version__ = SYFT_OBJECT_VERSION_1

    ip: str
    hostname: str
    network: str
    os: str
    connection_type: str
    connection_status: str
    is_online: bool


class TailscaleStatus(SyftObject):
    __canonical_name__ = "TailscaleStatus"
    __version__ = SYFT_OBJECT_VERSION_1

    state: TailScaleState
    peers: Optional[List[TailscalePeer]]
    host: TailscalePeer


@serializable()
class TailScaleClient(BaseVPNClient):
    connection: Type[NodeConnection]
    api_key: str

    def __init__(self, connection: Type[NodeConnection], api_key: str) -> None:
        self.connection = connection
        self.api_key = api_key

    @property
    def route(self) -> Any:
        return self.connection.route

    @staticmethod
    def _extract_host_and_peer(status_dict: dict) -> TailscaleStatus:
        def extract_peer_info(peer: Dict) -> Dict:
            info = dict()
            info["hostname"] = peer["HostName"]
            info["os"] = peer["OS"]
            info["ip"] = peer["TailscaleIPs"][0]
            info["is_online"] = peer["Online"]
            info["connection_status"] = (
                ConnectionStatus.ACTIVE if peer["Active"] else ConnectionStatus.IDLE
            )
            info["connection_type"] = (
                ConnectionType.DIRECT if peer["CurAddr"] else ConnectionType.RELAY
            )

            return info

        host_info = extract_peer_info(status_dict["Self"])

        state = status_dict["BackendState"]
        peers = []
        if not status_dict["Peer"]:
            for peer in status_dict["Peer"]:
                peer_info = extract_peer_info(peer=peer)
                peers.append(peer_info)

        return TailscaleStatus(
            state=TailScaleState[state],
            host=host_info,
            peers=peers,
        )

    def get_status(self) -> Union[SyftError, TailscaleStatus]:
        result = self.connection.send_command(
            path=self.route.SERVER_STATUS.value,
            api_key=self.api_key,
        )

        if result.is_err():
            return SyftError(message=result.err())

        command_report = result.ok()

        result = self.connection.resolve_report(
            api_key=self.api_key, report=command_report
        )

        if result.is_err():
            return SyftError(message=result.err())

        command_result = result.ok()

        if command_result.error:
            return SyftError(message=result.error)

        status_dict = json.loads(command_result.report)

        return self._extract_host_and_peer(status_dict=status_dict)

    def connect(
        self, headscale_host: str, headscale_auth_token: str
    ) -> Union[SyftSuccess, SyftError]:
        CONNECT_TIMEOUT = 60

        command_args = {
            "args": [
                "-login-server",
                f"{headscale_host}",
                "--reset",
                "--force-reauth",
                "--authkey",
                f"{headscale_auth_token}",
                "--accept-dns=false",
            ],
        }

        result = self.connection.send_command(
            path=self.route.SERVER_UP.value,
            api_key=self.api_key,
            timeout=CONNECT_TIMEOUT,
            command_args=command_args,
        )

        if result.is_err():
            return SyftError(message=result.err())

        command_report = result.ok()

        result = self.connection.resolve_report(
            api_key=self.api_key, report=command_report
        )

        if result.is_err():
            return SyftError(message=result.err())

        command_result = result.ok()

        if command_result.error:
            return SyftError(message=result.error)

        return SyftSuccess(message="Connection Successful !")

    def disconnect(self):
        DISCONNECT_TIMEOUT = 60

        result = self.connection.send_command(
            path=self.route.SERVER_DOWN.value,
            api_key=self.api_key,
            timeout=DISCONNECT_TIMEOUT,
        )

        if result.is_err():
            return SyftError(message=result.err())

        command_report = result.ok()

        result = self.connection.resolve_report(
            api_key=self.api_key, report=command_report
        )

        if result.is_err():
            return SyftError(message=result.err())

        command_result = result.ok()

        if command_result.error:
            return SyftError(message=result.error)

        return SyftSuccess(message="Disconnected Successfully !")
