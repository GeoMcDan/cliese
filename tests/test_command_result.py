def test_command_result():
    from testproj.typer import CommandResult

    result = CommandResult(0)
    assert result.exit_code == 0
    assert result.result == 0

    result = CommandResult(5)
    assert result.exit_code == 5
    assert result.result == 5

    result = CommandResult("some string")
    assert result.exit_code == 0
    assert result.result == "some string"

    result = CommandResult(None)
    assert result.exit_code == 0
    assert result.result is None
    print(result)
    assert repr(result) == "CommandResult(result=None, exit_code=0)"

    result = CommandResult("another string")
    result.exit_code = 3
    assert result.exit_code == 3
    assert result.result == "another string"
