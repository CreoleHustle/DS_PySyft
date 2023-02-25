# third party
import numpy as np
import pytest

# syft absolute
from syft.core.node.new.action_object import ActionObject


@pytest.fixture
def data1() -> ActionObject:
    """Returns an Action Object with a NumPy dataset with values between -1 and 1"""
    return ActionObject(syft_action_data=2 * np.random.rand(10, 10) - 1)


@pytest.fixture
def data2() -> ActionObject:
    """Returns an Action Object with a NumPy dataset with values between -1 and 1"""
    return ActionObject(syft_action_data=2 * np.random.rand(10, 10) - 1)


@pytest.fixture
def empty1(data1) -> ActionObject:
    """Returns an Empty Action Object corresponding to data1"""
    return ActionObject(syft_result_obj=np.array([]), id=data1.id)


@pytest.fixture
def empty2(data1) -> ActionObject:
    """Returns an Empty Action Object corresponding to data2"""
    return ActionObject(syft_result_obj=np.array([]), id=data2.id)


def test_add_private(data1: ActionObject, data2: ActionObject) -> None:
    """Test whether adding two ActionObjects produces the correct history hash"""
    result1 = data1 + data2
    result2 = data1 + data2
    result3 = data2 + data1

    assert result1.syft_history_hash == result2.syft_history_hash
    assert result3.syft_history_hash != result2.syft_history_hash


def test_op(data1: ActionObject, data2: ActionObject) -> None:
    """Ensure that using a different op will produce a different history hash"""
    result1 = data1 + data2
    result2 = data1 == data2

    assert result1.syft_history_hash != result2.syft_history_hash


def test_args(data1: ActionObject, data2: ActionObject) -> None:
    """Ensure that passing args results in different history hashes"""
    result1 = data1.std()
    result2 = data1.std(1)

    assert result1.syft_history_hash != result2.syft_history_hash

    result3 = data2 + 3
    result4 = data2 + 4
    assert result3.syft_history_hash != result4.syft_history_hash


def test_kwargs(data1: ActionObject) -> None:
    """Ensure that passing kwargs results in different history hashes"""
    result1 = data1.std()
    result2 = data1.std(axis=1)

    assert result1.syft_history_hash != result2.syft_history_hash


def test_args_kwargs_identical(data1: ActionObject) -> None:
    """Test that data.std(1) == data.std(axis=1) are the same"""
    result1 = data1.std(1)
    result2 = data1.std(axis=1)

    assert result1.syft_history_hash == result2.syft_history_hash


def test_trace_single_op(data1: ActionObject) -> None:
    """Test that we can recreate the correct history hash using TraceMode"""
    result1 = data1.std(axis=1)
    trace_result = ActionObject(syft_result_obj=np.array([]), id=data1.id).std(axis=1)

    assert result1.syft_history_hash == trace_result.syft_history_hash


def test_empty_arithmetic_hash(data1: ActionObject, empty1: ActionObject) -> None:
    """Test that we can recreate the correct hash history using Empty Objects"""
    result1 = data1 + data1

    assert result1.syft_history_hash == empty1.syft_history_hash


def test_empty_action_obj_hash_consistency(
    data1: ActionObject, empty1: ActionObject
) -> None:
    """Test that Empty Action Objects and regular Action Objects can work together"""

    result1 = data1 + empty1
    result2 = empty1 + data1

    assert result1.syft_history_hash == result2.syft_history_hash


def test_rinfix_add_empty_obj(data1: ActionObject, empty1: ActionObject) -> None:
    """Test that r infix operations like radd work with Empty ActionObjects"""
    assert (5 + empty1).syft_history_hash == (empty1 + 5).syft_history_hash
    assert (5 + empty1).syft_history_hash is not None
    assert (empty1 + 5).syft_history_hash is not None
    assert (5 + empty1).syft_history_hash == (data1 + 5).syft_history_hash
    assert (empty1 + 5).syft_history_hash == (5 + data1).syft_history_hash
    assert (5 + data1).syft_history_hash is not None
    assert (data1 + 5).syft_history_hash is not None
    assert (5 + data1).syft_history_hash == (data1 + 5).syft_history_hash


def test_empty_multiple_operations(data1: ActionObject, empty1: ActionObject) -> None:
    """Test that EmptyActionObjects are good for multiple operations"""
    step1 = data1.transpose()
    step2 = step1.std()
    step3 = step2.reshape((20, 5))
    target_hash = step3.syft_history_hash
    assert target_hash is not None

    empty1.transpose()
    step1.std()
    step2.reshape((20, 5))
    result_hash = step3.syft_history_hash
    assert result_hash is not None

    assert target_hash == result_hash


def test_history_hash_reproducibility(data1: ActionObject) -> None:
    """Test that the same history hash is produced, given the same inputs"""
    result1 = data1.mean(axis=1).std()
    result2 = data1.mean(axis=1).std()
    assert result1.syft_history_hash == result2.syft_history_hash

    mask = data1 > 0
    amount = data1 * 10
    result3 = mask * amount
    result4 = (data1 > 0) * (data1 * 10)
    assert result3.syft_history_hash == result4.syft_history_hash
