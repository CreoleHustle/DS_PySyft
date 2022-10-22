# stdlib
from enum import Enum


class GAMMA_TENSOR_OP(Enum):
    # Numpy ArrayLike
    NOOP = "noop"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    TRUE_DIVIDE = "true_divide"
    FLOOR_DIVIDE = "floor_divide"
    MATMUL = "matmul"
    RMATMUL = "rmatmul"
    GREATER = "greater"
    GREATER_EQUAL = "greater_equal"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    LESS = "less"
    LESS_EQUAL = "less_equal"
    EXP = "exp"
    LOG = "log"
    TRANSPOSE = "transpose"
    SUM = "sum"
    ONES_LIKE = "ones_like"
    ZEROS_LIKE = "zeros_like"
    RAVEL = "ravel"
    RESIZE = "resize"
    RESHAPE = "reshape"
    COMPRESS = "compress"
    SQUEEZE = "squeeze"
    ANY = "any"
    ALL = "all"
    LOGICAL_AND = "logical_and"
    LOGICAL_OR = "logical_or"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MEAN = "mean"
    CUMSUM = "cumsum"
    CUMPROD = "cumprod"
    STD = "std"
    VAR = "var"
    DOT = "dot"
    SQRT = "sqrt"
    ABS = "abs"
    CLIP = "clip"
    COPY = "copy"
    TAKE = "take"
    PUT = "put"
    ARGMAX = "argmax"
    ARGMIN = "argmin"
    PTP = "ptp"
    MOD = "mod"
    SWAPAXES = "swapaxes"
    NONZERO = "nonzero"
    PROD = "prod"
    POWER = "power"
    TRACE = "trace"
    MIN = "min"
    MAX = "max"
    REPEAT = "repeat"
    LSHIFT = "left_shift"
    RSHIFT = "right_shift"
    XOR = "bitwise_xor"
    ROUND = "round"
    SORT = "sort"
    ARGSORT = "argsort"
    # Our Methods
    RECIPROCAL = "reciprocal"
    FLATTEN_C = "flatten_c"
    FLATTEN_A = "flatten_a"
    FLATTEN_F = "flatten_f"
    FLATTEN_K = "flatten_k"
