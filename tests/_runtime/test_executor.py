from tests.conftest import ExecReqProvider, MockedKernel


def _has_output(messages: list[tuple[str, dict]], pattern: str) -> bool:
    """Returns True if any message matches the given pattern."""
    for op, data in messages:
        if (
            op == "cell-op"
            and data.get("output") is not None
            and data["output"].get("data") is not None
            and str(pattern) in str(data["output"]["data"])
        ):
            return True
    return False


async def test_semicolon_output_suppression(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    # Test that semicolon suppresses output for expressions
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                1 + 2;
                """
            )
        ]
    )
    assert not _has_output(mocked_kernel.stream.messages, "3")

    # Test that no semicolon shows output for expressions
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                2 + 3
                """
            )
        ]
    )
    assert _has_output(mocked_kernel.stream.messages, "5")

    # Test that comments after semicolon still suppress output
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                4 + 5; # comment
                """
            )
        ]
    )
    assert not _has_output(mocked_kernel.stream.messages, "9")

    # Test that assignments don't show output regardless of semicolon
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                x = 1
                """
            )
        ]
    )
    assert not _has_output(mocked_kernel.stream.messages, "1")

    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                y = 2;
                """
            )
        ]
    )
    assert not _has_output(mocked_kernel.stream.messages, "2")

    # Test that async cells respect semicolon suppression
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                import asyncio
                await asyncio.sleep(0);
                """
            )
        ]
    )
    assert not _has_output(mocked_kernel.stream.messages, "None")
