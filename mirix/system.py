import json
import uuid
from typing import Optional
import warnings

from .constants import (
    INITIAL_BOOT_MESSAGE,
    INITIAL_BOOT_MESSAGE_SEND_MESSAGE_FIRST_MSG,
    INITIAL_BOOT_MESSAGE_SEND_MESSAGE_THOUGHT,
    MESSAGE_SUMMARY_WARNING_STR,
)
from .utils import get_local_time, json_dumps


def get_initial_boot_messages(version="startup"):
    if version == "startup":
        initial_boot_message = INITIAL_BOOT_MESSAGE
        messages = [
            {"role": "assistant", "content": initial_boot_message},
        ]

    elif version == "startup_with_send_message":
        tool_call_id = str(uuid.uuid4())
        messages = [
            # first message includes both inner monologue and function call to send_message
            {
                "role": "assistant",
                "content": INITIAL_BOOT_MESSAGE_SEND_MESSAGE_THOUGHT,
                # "function_call": {
                #     "name": "send_message",
                #     "arguments": '{\n  "message": "' + f"{INITIAL_BOOT_MESSAGE_SEND_MESSAGE_FIRST_MSG}" + '"\n}',
                # },
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": "send_message",
                            "arguments": '{\n  "message": "' + f"{INITIAL_BOOT_MESSAGE_SEND_MESSAGE_FIRST_MSG}" + '"\n}',
                        },
                    }
                ],
            },
            # obligatory function return message
            {
                # "role": "function",
                "role": "tool",
                "name": "send_message",  # NOTE: technically not up to spec, this is old functions style
                "content": package_function_response(True, None),
                "tool_call_id": tool_call_id,
            },
        ]

    elif version == "startup_with_send_message_gpt35":
        tool_call_id = str(uuid.uuid4())
        messages = [
            # first message includes both inner monologue and function call to send_message
            {
                "role": "assistant",
                "content": "*inner thoughts* Still waiting on the user. Sending a message with function.",
                # "function_call": {"name": "send_message", "arguments": '{\n  "message": "' + f"Hi, is anyone there?" + '"\n}'},
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": "send_message",
                            "arguments": '{\n  "message": "' + f"Hi, is anyone there?" + '"\n}',
                        },
                    }
                ],
            },
            # obligatory function return message
            {
                # "role": "function",
                "role": "tool",
                "name": "send_message",
                "content": package_function_response(True, None),
                "tool_call_id": tool_call_id,
            },
        ]

    else:
        raise ValueError(version)

    return messages


def get_contine_chaining(reason="Automated timer", include_location=False, location_name="San Francisco, CA, USA"):
    # Package the message with time and location
    formatted_time = get_local_time()
    packaged_message = {
        "type": "contine_chaining",
        "reason": reason,
        "time": formatted_time,
    }

    if include_location:
        packaged_message["location"] = location_name

    return json_dumps(packaged_message)


def get_login_event(last_login="Never (first login)", include_location=False, location_name="San Francisco, CA, USA"):
    # Package the message with time and location
    formatted_time = get_local_time()
    packaged_message = {
        "type": "login",
        "last_login": last_login,
        "time": formatted_time,
    }

    if include_location:
        packaged_message["location"] = location_name

    return json_dumps(packaged_message)


def package_user_message(
    user_message: str,
    time: Optional[str] = None,
    include_location: bool = False,
    location_name: Optional[str] = "San Francisco, CA, USA",
    name: Optional[str] = None,
):
    # Package the message with time and location
    formatted_time = time if time else get_local_time()
    packaged_message = {
        "type": "user_message",
        "message": user_message,
        "time": formatted_time,
    }

    if include_location:
        packaged_message["location"] = location_name

    if name:
        packaged_message["name"] = name

    return json_dumps(packaged_message)


def package_function_response(was_success, response_string, timestamp=None):
    formatted_time = get_local_time() if timestamp is None else timestamp
    packaged_message = {
        "status": "OK" if was_success else "Failed",
        "message": response_string,
        "time": formatted_time,
    }

    return json_dumps(packaged_message)


def package_system_message(system_message, message_type="system_alert", time=None):
    formatted_time = time if time else get_local_time()
    packaged_message = {
        "type": message_type,
        "message": system_message,
        "time": formatted_time,
    }

    return json.dumps(packaged_message)


def package_summarize_message(summary, summary_message_count, hidden_message_count, total_message_count, timestamp=None):
    context_message = (
        f"Note: prior messages ({hidden_message_count} of {total_message_count} total messages) have been hidden from view due to conversation memory constraints.\n"
        + f"The following is a summary of the previous {summary_message_count} messages:\n {summary}"
    )

    formatted_time = get_local_time() if timestamp is None else timestamp
    packaged_message = {
        "type": "system_alert",
        "message": context_message,
        "time": formatted_time,
    }

    return json_dumps(packaged_message)


def package_summarize_message_no_summary(hidden_message_count, timestamp=None, message=None):
    """Add useful metadata to the summary message"""

    # Package the message with time and location
    formatted_time = get_local_time() if timestamp is None else timestamp
    context_message = (
        message
        if message
        else f"Note: {hidden_message_count} prior messages with the user have been hidden from view due to conversation memory constraints. Older messages are stored in Recall Memory and can be viewed using functions."
    )
    packaged_message = {
        "type": "system_alert",
        "message": context_message,
        "time": formatted_time,
    }

    return json_dumps(packaged_message)


def get_token_limit_warning():
    formatted_time = get_local_time()
    packaged_message = {
        "type": "system_alert",
        "message": MESSAGE_SUMMARY_WARNING_STR,
        "time": formatted_time,
    }

    return json_dumps(packaged_message)


def unpack_message(packed_message) -> str:
    """Take a packed message string and attempt to extract the inner message content"""

    try:
        message_json = json.loads(packed_message)
    except:
        warnings.warn(f"Was unable to load message as JSON to unpack: '{packed_message}'")
        return packed_message

    if "message" not in message_json:
        if "type" in message_json and message_json["type"] in ["login", "contine_chaining"]:
            # This is a valid user message that the ADE expects, so don't print warning
            return packed_message
        warnings.warn(f"Was unable to find 'message' field in packed message object: '{packed_message}'")
        return packed_message
    else:
        message_type = message_json["type"]
        if message_type != "user_message":
            warnings.warn(f"Expected type to be 'user_message', but was '{message_type}', so not unpacking: '{packed_message}'")
            return packed_message
        return message_json.get("message")
