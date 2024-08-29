from concurrent import futures
from typing import Callable, List, Any, Tuple


def execute_function_concurrently_with_args_list(
    function_to_execute: Callable[..., Any],
    list_of_argument_tuples: List[Tuple[Any, ...]],
    max_workers: int = 6
) -> None:
    """
    Executes a function concurrently with a list of argument tuples.

    :param func: The function to be executed concurrently.
    :param args_list: A list of tuples, each containing the arguments for a single call to `func`.
    :param max_workers: The maximum number of threads to use for concurrent execution. Default is 6.

    Example:
        `func` is a function that takes two arguments (a, b) and `args_list` is [(1, 2), (3, 4), (5, 6)].
        The function will execute `func(1, 2)`, `func(3, 4)`, and `func(5, 6)` concurrently.
    """
    with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures_list = [
            executor.submit(function_to_execute, *args)
            for args in list_of_argument_tuples
        ]

        # Re-raise any exceptions that occurred in the worker threads
        for future in futures.as_completed(futures_list):
            future.result()
