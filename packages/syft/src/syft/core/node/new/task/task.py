# stdlib
from typing import Any
from typing import Dict
from typing import List

# third party
from pydantic import BaseModel

# relative
from .....core.node.common.node_table.syft_object import SYFT_OBJECT_VERSION_1
from .....core.node.common.node_table.syft_object import SyftObject
from ....common.serde.serializable import serializable
from ....common.uid import UID
from ...abstract.node import AbstractNodeClient


@serializable(recursive_serde=True)
class NodeView(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    name: str
    node_uid: UID

    @staticmethod
    def from_client(client: AbstractNodeClient):
        return NodeView(name=client.name, node_uid=client.node_uid)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, NodeView):
            return False
        elif self.name == other.name and self.node_uid == other.uid:
            return True

    def __hash__(self) -> int:
        return hash((self.name, self.node_uid))


@serializable(recursive_serde=True)
class Task(SyftObject):
    # version
    __canonical_name__ = "Task"
    __version__ = SYFT_OBJECT_VERSION_1

    # fields
    user: str
    inputs: Dict[NodeView, dict]
    owner: List[NodeView]
    code: str
    status: Dict[NodeView, str]
    created_at: str
    updated_at: str
    reviewed_by: str
    execution: str
    outputs: Dict
    reason: str = ""

    # serde / storage rules
    __attr_state__ = [
        "id",
        "code",
        "user",
        "status",
        "inputs",
        "outputs",
        "created_at",
        "updated_at",
        "reviewed_by",
        "execution",
        "reason",
        "owner",
    ]

    __attr_searchable__ = ["id", "user"]
    __attr_unique__ = ["id"]
