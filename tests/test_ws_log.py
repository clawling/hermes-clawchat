from clawchat_gateway.ws_log import format_ws_log, optional_field


def test_format_ws_log_renders_fixed_field_order_and_placeholders():
    assert format_ws_log(
        event="auth_failed",
        account_id="default",
        attempt=2,
        reconnect_count=1,
        state="auth_failed",
        action="stop_reconnect",
        fields=[
            ("trace_id", "trace-1"),
            ("reason", ""),
        ],
    ) == (
        "clawchat.ws event=auth_failed account_id=default attempt=2 "
        "reconnect_count=1 state=auth_failed action=stop_reconnect "
        "trace_id=trace-1 reason=-"
    )


def test_optional_field_normalizes_absent_values():
    assert optional_field(None) == "-"
    assert optional_field("") == "-"
    assert optional_field("hello") == "hello"
    assert optional_field(0) == "0"
    assert optional_field(True) == "true"
    assert optional_field(False) == "false"
