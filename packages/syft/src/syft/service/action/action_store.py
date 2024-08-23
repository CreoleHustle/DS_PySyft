# future
from __future__ import annotations

# stdlib
import threading

# third party
from result import Err
from result import Ok
from result import Result

# relative
from ...serde.serializable import serializable
from ...server.credentials import SyftSigningKey
from ...server.credentials import SyftVerifyKey
from ...store.document_store import BasePartitionSettings
from ...store.document_store import DocumentStore
from ...store.document_store import StoreConfig
from ...types.syft_object import SyftObject
from ...types.twin_object import TwinObject
from ...types.uid import LineageID
from ...types.uid import UID
from ..response import SyftSuccess
from .action_object import is_action_data_empty
from .action_permissions import ActionObjectEXECUTE
from .action_permissions import ActionObjectOWNER
from .action_permissions import ActionObjectPermission
from .action_permissions import ActionObjectREAD
from .action_permissions import ActionObjectWRITE
from .action_permissions import ActionPermission
from .action_permissions import StoragePermission
from ...store.db.stash import ObjectStash
from .action_object import ActionObject


@serializable(canonical_name="ActionObjectSQLStore", version=1)
class ActionObjectStash(ObjectStash[ActionObject]):
    def get(
        self, uid: UID, credentials: SyftVerifyKey, has_permission: bool = False
    ) -> Result[ActionObject, str]:
        uid = uid.id  # We only need the UID from LineageID or UID

        # TODO remove and use get_by_uid instead
        result_or_err = self.get_by_uid(
            credentials=credentials,
            uid=uid,
            has_permission=has_permission,
        )
        if result_or_err.is_err():
            return Err(result_or_err.err())

        result = result_or_err.ok()
        if result is None:
            return Err(f"Could not find item with uid {uid}")
        return Ok(result)

    def get_mock(self, credentials: SyftVerifyKey, uid: UID) -> Result[SyftObject, str]:
        uid = uid.id  # We only need the UID from LineageID or UID

        try:
            syft_object = self.get_by_uid(
                credentials=credentials, uid=uid, has_permission=True
            )  # type: ignore
            if isinstance(syft_object, TwinObject) and not is_action_data_empty(
                syft_object.mock
            ):
                return Ok(syft_object.mock)
            return Err("No mock")
        except Exception as e:
            return Err(f"Could not find item with uid {uid}, {e}")

    def get_pointer(
        self,
        uid: UID,
        credentials: SyftVerifyKey,
        server_uid: UID,
    ) -> Result[SyftObject, str]:
        uid = uid.id  # We only need the UID from LineageID or UID

        try:
            result_or_err = self.get_by_uid(
                credentials=credentials, uid=uid, has_permission=True
            )
            has_permissions = self.has_permission(
                ActionObjectREAD(uid=uid, credentials=credentials)
            )
            if result_or_err.is_err():
                return Err(result_or_err.err())

            obj = result_or_err.ok()
            if obj is None:
                return Err("Permission denied")

            if has_permissions:
                if isinstance(obj, TwinObject):
                    return Ok(obj.private.syft_point_to(server_uid))
                return Ok(obj.syft_point_to(server_uid))

            # if its a twin with a mock anyone can have this
            if isinstance(obj, TwinObject):
                return Ok(obj.mock.syft_point_to(server_uid))

            # finally worst case you get ActionDataEmpty so you can still trace
            return Ok(obj.as_empty().syft_point_to(server_uid))

        except Exception as e:
            return Err(str(e))

    def exists(self, credentials: SyftVerifyKey, uid: UID) -> bool:
        uid = uid.id
        return super().exists(credentials=credentials, uid=uid)

    def set(
        self,
        uid: UID,
        credentials: SyftVerifyKey,
        syft_object: SyftObject,
        has_result_read_permission: bool = False,
        add_storage_permission: bool = True,
    ) -> Result[SyftSuccess, Err]:
        uid = uid.id  # We only need the UID from LineageID or UID

        # if you set something you need WRITE permission
        write_permission = ActionObjectWRITE(uid=uid, credentials=credentials)
        can_write = self.has_permission(write_permission)

        if not self.exists(credentials=credentials, uid=uid):
            # attempt to claim it for writing
            if has_result_read_permission:
                ownership_result = self.take_ownership(uid=uid, credentials=credentials)
                can_write = True if ownership_result.is_ok() else False
            else:
                # root takes owneship, but you can still write
                ownership_result = self.take_ownership(
                    uid=uid, credentials=self.root_verify_key
                )
                can_write = True if ownership_result.is_ok() else False

        if can_write:
            self.data[uid] = syft_object
            if uid not in self.permissions:
                # create default permissions
                self.permissions[uid] = set()
            if has_result_read_permission:
                self.add_permission(ActionObjectREAD(uid=uid, credentials=credentials))
            else:
                self.add_permissions(
                    [
                        ActionObjectWRITE(uid=uid, credentials=credentials),
                        ActionObjectEXECUTE(uid=uid, credentials=credentials),
                    ]
                )

            if uid not in self.storage_permissions:
                # create default storage permissions
                self.storage_permissions[uid] = set()
            if add_storage_permission:
                self.add_storage_permission(
                    StoragePermission(uid=uid, server_uid=self.server_uid)
                )

            return Ok(SyftSuccess(message=f"Set for ID: {uid}"))
        return Err(f"Permission: {write_permission} denied")

    def take_ownership(
        self, uid: UID, credentials: SyftVerifyKey
    ) -> Result[SyftSuccess, str]:
        uid = uid.id  # We only need the UID from LineageID or UID

        # first person using this UID can claim ownership
        if uid not in self.permissions and uid not in self.data:
            self.add_permissions(
                [
                    ActionObjectOWNER(uid=uid, credentials=credentials),
                    ActionObjectWRITE(uid=uid, credentials=credentials),
                    ActionObjectREAD(uid=uid, credentials=credentials),
                    ActionObjectEXECUTE(uid=uid, credentials=credentials),
                ]
            )
            return Ok(SyftSuccess(message=f"Ownership of ID: {uid} taken."))
        return Err(f"UID: {uid} already owned.")

    def delete(self, uid: UID, credentials: SyftVerifyKey) -> Result[SyftSuccess, str]:
        uid = uid.id  # We only need the UID from LineageID or UID

        # if you delete something you need OWNER permission
        # is it bad to evict a key and have someone else reuse it?
        # perhaps we should keep permissions but no data?
        owner_permission = ActionObjectOWNER(uid=uid, credentials=credentials)
        if self.has_permission(owner_permission):
            if uid in self.data:
                del self.data[uid]
            if uid in self.permissions:
                del self.permissions[uid]
            return Ok(SyftSuccess(message=f"ID: {uid} deleted"))
        return Err(f"Permission: {owner_permission} denied")

    def _has_permission(self, permission: ActionObjectPermission) -> bool:
        if not isinstance(permission.permission, ActionPermission):
            raise Exception(f"ObjectPermission type: {permission.permission} not valid")

        if (
            permission.credentials is not None
            and self.root_verify_key.verify == permission.credentials.verify
        ):
            return True

        if self.__user_stash is not None:
            # relative
            from ...service.user.user_roles import ServiceRole

            res = self.__user_stash.get_by_verify_key(
                credentials=permission.credentials,
                verify_key=permission.credentials,
            )

            if (
                res.is_ok()
                and (user := res.ok()) is not None
                and user.role in (ServiceRole.DATA_OWNER, ServiceRole.ADMIN)
            ):
                return True

        if (
            permission.uid in self.permissions
            and permission.permission_string in self.permissions[permission.uid]
        ):
            return True

        # 🟡 TODO 14: add ALL_READ, ALL_EXECUTE etc
        if permission.permission == ActionPermission.OWNER:
            pass
        elif permission.permission == ActionPermission.READ:
            pass
        elif permission.permission == ActionPermission.WRITE:
            pass
        elif permission.permission == ActionPermission.EXECUTE:
            pass

        return False

    def has_permissions(self, permissions: list[ActionObjectPermission]) -> bool:
        return all(self.has_permission(p) for p in permissions)

    def add_permission(self, permission: ActionObjectPermission) -> None:
        permissions = self.permissions[permission.uid]
        permissions.add(permission.permission_string)
        self.permissions[permission.uid] = permissions

    def remove_permission(self, permission: ActionObjectPermission) -> None:
        permissions = self.permissions[permission.uid]
        permissions.remove(permission.permission_string)
        self.permissions[permission.uid] = permissions

    def add_permissions(self, permissions: list[ActionObjectPermission]) -> None:
        for permission in permissions:
            self.add_permission(permission)

    def _get_permissions_for_uid(self, uid: UID) -> Result[set[str], str]:
        if uid in self.permissions:
            return Ok(self.permissions[uid])
        return Err(f"No permissions found for uid: {uid}")

    def get_all_permissions(self) -> Result[dict[UID, set[str]], str]:
        return Ok(dict(self.permissions.items()))

    def add_storage_permission(self, permission: StoragePermission) -> None:
        permissions = self.storage_permissions[permission.uid]
        permissions.add(permission.server_uid)
        self.storage_permissions[permission.uid] = permissions

    def add_storage_permissions(self, permissions: list[StoragePermission]) -> None:
        for permission in permissions:
            self.add_storage_permission(permission)

    def remove_storage_permission(self, permission: StoragePermission) -> None:
        permissions = self.storage_permissions[permission.uid]
        permissions.remove(permission.server_uid)
        self.storage_permissions[permission.uid] = permissions

    def has_storage_permission(self, permission: StoragePermission | UID) -> bool:
        if isinstance(permission, UID):
            permission = StoragePermission(uid=permission, server_uid=self.server_uid)

        if permission.uid in self.storage_permissions:
            return permission.server_uid in self.storage_permissions[permission.uid]
        return False

    def _get_storage_permissions_for_uid(self, uid: UID) -> Result[set[UID], str]:
        if uid in self.storage_permissions:
            return Ok(self.storage_permissions[uid])
        return Err(f"No storage permissions found for uid: {uid}")

    def get_all_storage_permissions(self) -> Result[dict[UID, set[UID]], str]:
        return Ok(dict(self.storage_permissions.items()))

    def _all(
        self,
        credentials: SyftVerifyKey,
        has_permission: bool | None = False,
    ) -> Result[list[SyftObject], str]:
        # this checks permissions
        res = [self.get(uid, credentials, has_permission) for uid in self.data.keys()]
        result = [x.ok() for x in res if x.is_ok()]
        return Ok(result)

    def migrate_data(
        self, to_klass: SyftObject, credentials: SyftVerifyKey
    ) -> Result[bool, str]:
        has_root_permission = credentials == self.root_verify_key

        if has_root_permission:
            for key, value in self.data.items():
                try:
                    if value.__canonical_name__ != to_klass.__canonical_name__:
                        continue
                    migrated_value = value.migrate_to(to_klass.__version__)
                except Exception as e:
                    return Err(
                        f"Failed to migrate data to {to_klass} {to_klass.__version__} for qk: {key}. Exception: {e}"
                    )
                result = self.set(
                    uid=key,
                    credentials=credentials,
                    syft_object=migrated_value,
                )

                if result.is_err():
                    return result.err()

            return Ok(True)

        return Err("You don't have permissions to migrate data.")
