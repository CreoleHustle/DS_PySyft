# third party

# third party
import numpy as np

# syft absolute
import syft
import syft as sy
from syft.client.domain_client import DomainClient
from syft.client.sync_decision import SyncDecision
from syft.client.syncing import compare_clients
from syft.client.syncing import resolve
from syft.node.worker import Worker
from syft.service.job.job_stash import Job
from syft.service.request.request import RequestStatus
from syft.service.response import SyftError
from syft.service.response import SyftSuccess
from syft.service.sync.resolve_widget import ResolveWidget


def handle_decision(
    widget: ResolveWidget, decision: SyncDecision
) -> SyftSuccess | SyftError:
    if decision == SyncDecision.IGNORE:
        # ignore not yet implemented on the widget
        return widget.obj_diff_batch.ignore()
    elif decision in [SyncDecision.LOW, SyncDecision.HIGH]:
        return widget.click_sync()
    elif decision == SyncDecision.SKIP:
        # Skip is no-op
        return SyftSuccess(message="skipped")
    else:
        raise ValueError(f"Unknown decision {decision}")


def compare_and_resolve(
    *,
    from_client: DomainClient,
    to_client: DomainClient,
    decision: SyncDecision = SyncDecision.LOW,
    decision_callback: callable = None,
    share_private_data: bool = True,
):
    diff_state_before = compare_clients(from_client, to_client)
    for obj_diff_batch in diff_state_before.active_batches:
        widget = resolve(
            obj_diff_batch,
        )
        if decision_callback:
            decision = decision_callback(obj_diff_batch)
        if share_private_data:
            widget.click_share_all_private_data()
        res = handle_decision(widget, decision)
        assert isinstance(res, SyftSuccess)
    from_client.refresh()
    to_client.refresh()
    diff_state_after = compare_clients(from_client, to_client)
    return diff_state_before, diff_state_after


def run_and_deposit_result(client):
    result = client.code.compute(blocking=True)
    job = client.requests[0].deposit_result(result)
    return job


def create_dataset(client):
    mock = np.random.random(5)
    private = np.random.random(5)

    dataset = sy.Dataset(
        name=sy.util.util.random_name().lower(),
        description="Lorem ipsum dolor sit amet, consectetur adipiscing elit",
        asset_list=[
            sy.Asset(
                name="numpy-data",
                mock=mock,
                data=private,
                shape=private.shape,
                mock_is_real=True,
            )
        ],
    )

    client.upload_dataset(dataset)
    return dataset


@syft.syft_function_single_use()
def compute() -> int:
    return 42


def get_ds_client(client: DomainClient) -> DomainClient:
    client.register(
        name="a",
        email="a@a.com",
        password="asdf",
        password_verify="asdf",
    )
    return client.login(email="a@a.com", password="asdf")


def test_diff_state(low_worker, high_worker):
    low_client: DomainClient = low_worker.root_client
    client_low_ds = get_ds_client(low_client)
    high_client: DomainClient = high_worker.root_client

    @sy.syft_function_single_use()
    def compute() -> int:
        return 42

    _ = client_low_ds.code.request_code_execution(compute)

    diff_state_before, diff_state_after = compare_and_resolve(
        from_client=low_client, to_client=high_client
    )

    assert not diff_state_before.is_same

    assert diff_state_after.is_same

    run_and_deposit_result(high_client)
    diff_state_before, diff_state_after = compare_and_resolve(
        from_client=high_client, to_client=low_client
    )

    high_state = high_client.get_sync_state()
    low_state = high_client.get_sync_state()
    assert high_state.get_previous_state_diff().is_same
    assert low_state.get_previous_state_diff().is_same
    assert diff_state_after.is_same

    client_low_ds.refresh()
    res = client_low_ds.code.compute(blocking=True)
    assert res == compute(syft_no_node=True)


def test_diff_state_with_dataset(low_worker: Worker, high_worker: Worker):
    low_client: DomainClient = low_worker.root_client
    client_low_ds = get_ds_client(low_client)
    high_client: DomainClient = high_worker.root_client

    _ = create_dataset(high_client)

    @sy.syft_function_single_use()
    def compute_mean(data) -> int:
        return data.mean()

    _ = client_low_ds.code.request_code_execution(compute_mean)

    result = client_low_ds.code.compute_mean(blocking=False)
    assert isinstance(
        result, SyftError
    ), "DS cannot start a job on low side since the data was not passed as an argument"

    diff_state_before, diff_state_after = compare_and_resolve(
        from_client=low_client, to_client=high_client
    )

    assert not diff_state_before.is_same

    assert diff_state_after.is_same

    # run_and_deposit_result(high_client)
    data_high = high_client.datasets[0].assets[0]
    mean_result = high_client.code.compute_mean(data=data_high, blocking=True)
    high_client.requests[0].deposit_result(mean_result)

    # the high side client delete the dataset after depositing the result
    dataset_del_res = high_client.api.services.dataset.delete_by_uid(
        high_client.datasets[0].id
    )
    assert isinstance(dataset_del_res, SyftSuccess)

    diff_state_before, diff_state_after = compare_and_resolve(
        from_client=high_client, to_client=low_client
    )

    high_state = high_client.get_sync_state()
    low_state = high_client.get_sync_state()
    assert high_state.get_previous_state_diff().is_same
    assert low_state.get_previous_state_diff().is_same
    assert diff_state_after.is_same

    client_low_ds.refresh()

    # check loading results for both blocking and non-blocking case
    res_blocking = client_low_ds.code.compute_mean(blocking=True)
    res_non_blocking = client_low_ds.code.compute_mean(blocking=False).wait()

    # expected_result = compute_mean(syft_no_node=True, data=)
    assert res_blocking == res_non_blocking == mean_result


def test_sync_with_error(low_worker, high_worker):
    """Check syncing with an error in a syft function"""
    low_client: DomainClient = low_worker.root_client
    client_low_ds = get_ds_client(low_client)
    high_client: DomainClient = high_worker.root_client

    @sy.syft_function_single_use()
    def compute() -> int:
        raise RuntimeError
        return 42

    _ = client_low_ds.code.request_code_execution(compute)

    diff_state_before, diff_state_after = compare_and_resolve(
        from_client=low_client, to_client=high_client
    )

    assert not diff_state_before.is_same

    assert diff_state_after.is_same

    run_and_deposit_result(high_client)
    diff_state_before, diff_state_after = compare_and_resolve(
        from_client=high_client, to_client=low_client
    )

    assert not diff_state_before.is_same
    assert diff_state_after.is_same

    client_low_ds.refresh()
    res = client_low_ds.code.compute(blocking=True)
    assert isinstance(res.get(), SyftError)


def test_ignore_unignore_single(low_worker, high_worker):
    low_client: DomainClient = low_worker.root_client
    client_low_ds = get_ds_client(low_client)
    high_client: DomainClient = high_worker.root_client

    @sy.syft_function_single_use()
    def compute() -> int:
        return 42

    _ = client_low_ds.code.request_code_execution(compute)

    diff = compare_clients(low_client, high_client, hide_usercode=False)

    assert len(diff.batches) == 2  # Request + UserCode
    assert len(diff.ignored_batches) == 0

    # Ignore usercode, request also gets ignored
    res = diff[0].ignore()
    assert isinstance(res, SyftSuccess)

    diff = compare_clients(low_client, high_client, hide_usercode=False)
    assert len(diff.batches) == 0
    assert len(diff.ignored_batches) == 2
    assert len(diff.all_batches) == 2

    # Unignore usercode
    res = diff.ignored_batches[0].unignore()
    assert isinstance(res, SyftSuccess)

    diff = compare_clients(low_client, high_client, hide_usercode=False)
    assert len(diff.batches) == 1
    assert len(diff.ignored_batches) == 1
    assert len(diff.all_batches) == 2


def test_request_code_execution_multiple(low_worker, high_worker):
    low_client = low_worker.root_client
    client_low_ds = low_worker.guest_client
    high_client = high_worker.root_client

    @sy.syft_function_single_use()
    def compute() -> int:
        return 42

    @sy.syft_function_single_use()
    def compute_twice() -> int:
        return 42 * 2

    @sy.syft_function_single_use()
    def compute_thrice() -> int:
        return 42 * 3

    _ = client_low_ds.code.request_code_execution(compute)
    _ = client_low_ds.code.request_code_execution(compute_twice)

    diff_before, diff_after = compare_and_resolve(
        from_client=low_client, to_client=high_client
    )

    assert not diff_before.is_same
    assert diff_after.is_same

    _ = client_low_ds.code.request_code_execution(compute_thrice)

    diff_before, diff_after = compare_and_resolve(
        from_client=low_client, to_client=high_client
    )

    assert not diff_before.is_same
    assert diff_after.is_same


def test_approve_request_on_sync_blocking(low_worker, high_worker):
    low_client = low_worker.root_client
    client_low_ds = get_ds_client(low_client)
    high_client = high_worker.root_client

    @sy.syft_function_single_use()
    def compute() -> int:
        return 42

    _ = client_low_ds.code.request_code_execution(compute)

    # No execute permissions
    result_error = client_low_ds.code.compute(blocking=True)
    assert isinstance(result_error, SyftError)
    assert low_client.requests[0].status == RequestStatus.PENDING

    # Sync request to high side
    diff_before, diff_after = compare_and_resolve(
        from_client=low_client, to_client=high_client
    )

    assert not diff_before.is_same
    assert diff_after.is_same

    # Execute on high side
    job = run_and_deposit_result(high_client)
    assert job.result.get() == 42

    assert high_client.requests[0].status == RequestStatus.PENDING

    # Sync back to low side, share private data
    diff_before, diff_after = compare_and_resolve(
        from_client=high_client, to_client=low_client, share_private_data=True
    )
    assert len(diff_before.batches) == 1 and diff_before.batches[0].root_type is Job
    assert low_client.requests[0].status == RequestStatus.APPROVED

    assert client_low_ds.code.compute().get() == 42
    assert len(client_low_ds.code.compute.jobs) == 1
    # check if user retrieved from cache, instead of re-executing
    assert len(client_low_ds.requests[0].code.output_history) == 1


def test_deny_and_sync(low_worker, high_worker):
    low_client = low_worker.root_client
    client_low_ds = get_ds_client(low_client)
    high_client = high_worker.root_client

    @sy.syft_function_single_use()
    def compute() -> int:
        return 42

    _ = client_low_ds.code.request_code_execution(compute)

    # No execute permissions
    result_error = client_low_ds.code.compute(blocking=True)
    assert isinstance(result_error, SyftError)
    assert low_client.requests[0].status == RequestStatus.PENDING

    # Deny on low side
    request_low = low_client.requests[0]
    res = request_low.deny(reason="bad request")
    print(res)
    assert low_client.requests[0].status == RequestStatus.REJECTED

    # Un-deny. NOTE: not supported by current UX, this is just used to re-deny on high side
    low_client.api.code.update(id=request_low.code_id, l0_deny_reason=None)
    assert low_client.requests[0].status == RequestStatus.PENDING

    # Sync request to high side
    diff_before, diff_after = compare_and_resolve(
        from_client=low_client, to_client=high_client
    )

    assert not diff_before.is_same
    assert diff_after.is_same

    # Deny on high side
    high_client.requests[0].deny(reason="bad request")
    assert high_client.requests[0].status == RequestStatus.REJECTED

    diff_before, diff_after = compare_and_resolve(
        from_client=high_client, to_client=low_client
    )

    assert diff_after.is_same

    assert low_client.requests[0].status == RequestStatus.REJECTED
