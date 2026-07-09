"""Pure movement speed and packet policy for behavior dummies."""

from __future__ import annotations

import argparse


DAOC_PACKET_SPEED_SCALE = 256.0


def dummy_coerce_world_movement_speed(speed: float | None) -> float | None:
    if speed is None:
        return None
    value = float(speed)
    if value <= 0:
        return value
    if value >= 4096:
        return value / DAOC_PACKET_SPEED_SCALE
    return value


def dummy_state_movement_cap(args: argparse.Namespace, client=None) -> float | None:
    """Return the server-authoritative movement cap from max_speed_percent."""
    base = getattr(args, "base_movement_speed", None)
    if base is None:
        base = getattr(args, "movement_speed", None)
    if base is None:
        return None

    percent = 100.0
    if client is not None and hasattr(client, "max_speed_percent"):
        percent = float(client.max_speed_percent)
    elif getattr(args, "movement_speed", None) is not None and getattr(args, "base_movement_speed", None) is not None:
        return float(args.movement_speed)

    return float(base) * percent / 100.0


def dummy_clamp_to_state_cap(
    args: argparse.Namespace,
    speed: float | None,
    client=None,
    *,
    clamp_to_state_cap: bool = True,
) -> float | None:
    coerced = dummy_coerce_world_movement_speed(speed)
    if coerced is None or coerced <= 0:
        return coerced

    if not clamp_to_state_cap:
        return coerced

    cap = dummy_state_movement_cap(args, client)
    if cap is None or cap <= 0:
        return coerced
    return min(coerced, cap)


def dummy_travel_movement_speed(
    args: argparse.Namespace,
    movement_speed: float | None = None,
    client=None,
    *,
    clamp_to_state_cap: bool = True,
) -> float | None:
    if movement_speed is not None:
        return dummy_clamp_to_state_cap(args, movement_speed, client, clamp_to_state_cap=clamp_to_state_cap)
    configured = getattr(args, "movement_speed", None)
    if configured is None:
        return None
    return dummy_coerce_world_movement_speed(float(configured))


def dummy_packet_movement_speed(travel_speed: float | None) -> float | None:
    if travel_speed is None:
        return None
    return dummy_coerce_world_movement_speed(travel_speed)


def dummy_movement_step_seconds(args: argparse.Namespace) -> float:
    if getattr(args, "smooth_movement", False) and float(getattr(args, "smooth_move_interval", 0.0) or 0.0) > 0.0:
        return float(args.smooth_move_interval)
    interval = float(getattr(args, "movement_update_interval", 0.0) or 0.0)
    if interval > 0.0:
        return interval
    return 0.2


def dummy_movement_kwargs(
    args: argparse.Namespace,
    movement_speed: float | None = None,
    client=None,
    *,
    clamp_to_state_cap: bool = True,
) -> dict[str, float | None]:
    travel = dummy_travel_movement_speed(args, movement_speed, client, clamp_to_state_cap=clamp_to_state_cap)
    return {
        "movement_speed": travel,
        "packet_speed": dummy_packet_movement_speed(travel),
        "min_position_send_interval": getattr(args, "movement_update_interval", 0.0),
        "movement_step_seconds": dummy_movement_step_seconds(args),
        "use_elapsed_movement_time": True,
        "max_elapsed_movement_seconds": 1.5,
    }
