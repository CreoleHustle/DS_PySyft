# stdlib

# third party
from syft.store.document_store_errors import NotFoundException, StashException
from syft.types.result import as_result

# relative
from ...node.credentials import SyftVerifyKey
from ...serde.serializable import serializable
from ...store.document_store import BaseUIDStoreStash, NewBaseUIDStoreStash
from ...store.document_store import DocumentStore
from ...store.document_store import PartitionSettings
from ...store.document_store import QueryKeys
from .policy import PolicyUserVerifyKeyPartitionKey
from .policy import UserPolicy


@serializable()
class UserPolicyStash(NewBaseUIDStoreStash):
    object_type = UserPolicy
    settings: PartitionSettings = PartitionSettings(
        name=UserPolicy.__canonical_name__, object_type=UserPolicy
    )

    def __init__(self, store: DocumentStore) -> None:
        super().__init__(store=store)

    @as_result(StashException, NotFoundException)
    def get_all_by_user_verify_key(
        self, credentials: SyftVerifyKey, user_verify_key: SyftVerifyKey
    ) -> list[UserPolicy]:
        qks = QueryKeys(qks=[PolicyUserVerifyKeyPartitionKey.with_obj(user_verify_key)])
        return self.query_one(credentials=credentials, qks=qks).unwrap()
