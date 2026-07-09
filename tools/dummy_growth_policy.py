"""Pure target and carry policy for dummy growth runs."""

from __future__ import annotations


def target_levels(level: int, party_size: int, realm_key: str = "") -> tuple[int, int, int]:
    player_level = max(1, min(level, 50))
    if player_level <= 1:
        if party_size <= 1:
            return 0, 0, 1
        if party_size <= 4:
            return 1, 1, 0
        if realm_key == "hib":
            return 1, 1, 0
        return 1, 1, 0

    if player_level < 5:
        if party_size <= 1:
            if player_level == 2:
                return 1, 1, 0
            if realm_key == "hib" and player_level == 3:
                return 1, 1, 0
            if player_level == 3:
                return 2, 2, 0
            if player_level == 4:
                return 2, 2, 0
            return max(1, player_level - 2), player_level, 0
        if realm_key == "hib" and player_level == 3 and party_size == 2:
            return 2, 3, 1
        if realm_key == "hib" and player_level == 3 and party_size >= 8:
            return 1, 2, 1
        if realm_key == "mid" and party_size >= 8 and player_level >= 3:
            if player_level == 3:
                return 2, 3, 1
            return player_level, player_level, 0
        if party_size <= 2:
            target = max(1, player_level - 1)
            return target, target, 0
        if party_size <= 4:
            target = max(1, player_level - 1)
            return target, player_level, 0
        target = max(1, player_level - 1)
        return target, player_level, 0

    if player_level == 5 and party_size <= 1:
        if realm_key == "alb":
            return 3, 3, 0
        if realm_key == "mid":
            return 3, 3, 0
        if realm_key == "hib":
            return 4, 4, 0
        return 2, 2, 0

    if realm_key == "hib" and party_size <= 1 and player_level == 11:
        return 7, 8, 1

    if 5 <= player_level <= 10 and party_size > 1:
        if party_size <= 2:
            if realm_key == "mid" and player_level == 5:
                return 4, 5, 1
            if realm_key == "mid" and player_level == 6:
                return 4, 5, 1
            if realm_key == "alb" and player_level == 6:
                return 5, 6, 1
            if realm_key == "alb" and player_level == 7:
                return 5, 6, 1
            elif realm_key == "hib" and player_level == 8:
                return 7, 8, 0
            elif realm_key == "mid" and player_level == 7:
                return 5, 6, 1
            elif realm_key == "mid" and player_level == 8:
                return 6, 7, 1
            elif player_level <= 5:
                target = 4
            elif player_level <= 9:
                target = max(1, player_level - 2)
            else:
                target = 7
        elif party_size <= 4:
            if realm_key == "mid" and player_level == 5:
                return 4, 5, 1
            if realm_key == "mid" and player_level == 6:
                return 4, 5, 1
            if realm_key == "alb" and player_level == 7:
                return 5, 6, 1
            if realm_key == "mid" and player_level == 9:
                return 8, 8, 0
            if realm_key == "hib" and player_level == 10:
                return 10, 10, 0
            if realm_key == "hib" and player_level == 9:
                return 8, 8, 0
            if realm_key == "hib" and player_level == 8:
                target = 7
            elif realm_key == "alb" and player_level == 6:
                target = 5
            elif realm_key == "mid" and player_level == 7:
                target = 7
            elif player_level <= 5:
                target = 4
            elif player_level <= 7:
                target = 5
            elif player_level <= 9:
                target = max(1, player_level - 2)
            else:
                target = 8
        else:
            if realm_key == "alb" and party_size >= 8 and player_level == 5:
                return 4, 4, 0
            target = player_level
            return target, target, 1
        return target, target, 0

    if player_level == 6 and party_size <= 1:
        if realm_key == "alb":
            return 4, 4, 0
        return 4, 4, 0

    if player_level == 7 and party_size <= 1 and realm_key == "alb":
        return 5, 5, 0

    if player_level == 7 and party_size <= 1 and realm_key == "mid":
        return 6, 6, 0

    if player_level in {7, 8} and party_size <= 1 and realm_key == "hib":
        return 5, 6, 1

    if player_level <= 7 and party_size <= 1:
        target = max(1, player_level - 1)
        return target, target, 0

    if player_level == 8 and party_size <= 1 and realm_key == "alb":
        return 6, 6, 0

    if player_level == 8 and party_size <= 1 and realm_key == "mid":
        return 6, 7, 1

    if player_level == 8 and party_size <= 1:
        return 6, 6, 0

    if player_level == 9 and party_size <= 1 and realm_key == "alb":
        return 7, 7, 0

    if player_level == 9 and party_size <= 1 and realm_key == "mid":
        return 7, 8, 1

    if player_level == 10 and party_size <= 1 and realm_key == "mid":
        return 7, 7, 0

    if player_level <= 10 and party_size <= 1:
        target = max(1, player_level - 2)
        if realm_key == "hib" and player_level == 9:
            return 6, 6, 0
        if realm_key == "hib" and player_level == 10:
            return 6, 6, 0
        if realm_key == "alb" and player_level == 10:
            return 7, 7, 0
        if player_level == 10:
            return max(1, target - 1), target, 1
        return max(1, target - 1), target, 0

    if player_level >= 50:
        if party_size <= 2:
            return 46, 47, 1
        return 46, 48, 2

    ideal_bonus = 1 if party_size == 1 else 1 if party_size <= 2 else 2 if party_size <= 4 else 3
    max_delta = 1 if party_size == 1 else 2 if party_size <= 2 else 3 if party_size <= 4 else 5
    return max(1, player_level - 1), min(50, player_level + ideal_bonus), max_delta


def uses_level_one_starter_survival_tuning(level: int, party_size: int) -> bool:
    return max(1, int(level or 1)) <= 1 and int(party_size or 0) <= 2


def uses_low_solo_flee_tuning(level: int, party_size: int, realm_key: str = "") -> bool:
    realm = str(realm_key or "").lower()
    player_level = max(1, int(level or 1))
    return uses_level_one_starter_survival_tuning(level, party_size) or (
        int(party_size or 0) <= 1 and realm == "hib" and player_level == 4
    )


def uses_low_small_party_commit_tuning(level: int, party_size: int, realm_key: str = "") -> bool:
    del realm_key
    player_level = max(1, int(level or 1))
    return 2 <= int(party_size or 0) <= 4 and 4 <= player_level <= 7


def uses_hib_low_duo_recovery_tuning(level: int, party_size: int, realm_key: str = "") -> bool:
    return str(realm_key or "").lower() == "hib" and int(party_size or 0) == 2 and max(1, int(level or 1)) <= 2


def uses_growth_party_carry_tuning(level: int, party_size: int) -> bool:
    del level
    return int(party_size or 0) > 1


def growth_party_carry_count(party_size: int) -> int:
    if int(party_size or 0) <= 1:
        return 0
    return max(1, int(party_size or 0) - 1)


def growth_party_carry_party_slots(party_size: int) -> list[int]:
    return list(range(growth_party_carry_count(party_size)))


GROWTH_PARTY_CARRY_GREY_SPANS_BY_PLAYER_LEVEL = (
    0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 7, 7, 7, 8, 9, 10, 11,
    12, 13, 14, 14, 14, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
    24, 25, 26, 26, 26, 26, 26, 26, 26, 27, 28, 29, 30, 31, 32,
    33, 34, 35, 36,
)


def growth_party_carry_max_non_grey_level_for_target(target_level: int) -> int:
    target = max(1, int(target_level or 1))
    max_level = 1
    for player_level, grey_span in enumerate(GROWTH_PARTY_CARRY_GREY_SPANS_BY_PLAYER_LEVEL):
        if player_level <= 0:
            continue
        if target >= grey_span:
            max_level = player_level
    return min(50, max_level)


def growth_party_carry_target_gap(party_size: int) -> int:
    if int(party_size or 0) >= 8:
        return 10
    if int(party_size or 0) >= 4:
        return 8
    if int(party_size or 0) >= 2:
        return 5
    return 0


def growth_party_carry_target_gap_for_level(tracked_level: int, party_size: int) -> int:
    party = int(party_size or 0)
    if party <= 1:
        return 0
    level = max(1, int(tracked_level or 1))
    if level <= 4:
        if party >= 8:
            if level <= 2:
                return 5
            return 3
        if party >= 4:
            return 3 if level <= 1 else 2
        return 2 if level <= 1 else 1
    if level <= 6:
        if party >= 8:
            return 3
        if party >= 4:
            return 2
        return 1
    if level <= 8:
        if party >= 8:
            return 4
        if party >= 4:
            return 3
        return 2
    if level <= 10:
        if party >= 8:
            return 5
        if party >= 4:
            return 4
        return 3
    return growth_party_carry_target_gap(party)


def growth_party_carry_challenge_target_offset(party_size: int) -> int:
    del party_size
    return 0


def growth_party_carry_level_bonus(party_size: int) -> int:
    party = int(party_size or 0)
    if party <= 1:
        return 0
    if party >= 8:
        return 6
    return 5


def growth_party_carry_target_level(tracked_level: int, party_size: int) -> int:
    player_level = max(1, int(tracked_level or 1))
    if int(party_size or 0) <= 1:
        return player_level
    target_level = max(1, player_level + growth_party_carry_target_gap_for_level(player_level, party_size))
    return min(50, target_level)


def growth_party_carry_base_level(tracked_level: int, party_size: int) -> int:
    target_level = growth_party_carry_target_level(tracked_level, party_size)
    if int(party_size or 0) <= 1:
        return target_level
    challenge_offset = growth_party_carry_challenge_target_offset(party_size)
    level_bonus = growth_party_carry_level_bonus(party_size)
    return min(49, max(1, target_level - challenge_offset + level_bonus))


def growth_party_carry_level_for_party(tracked_level: int, party_size: int) -> int:
    return growth_party_carry_base_level(tracked_level, party_size)


def growth_party_carry_target_plan(tracked_level: int, party_size: int = 0) -> tuple[int, int, int]:
    target = growth_party_carry_target_level(tracked_level, party_size)
    party = int(party_size or 0)
    level = max(1, int(tracked_level or 1))
    min_target_fallback = 1 if 1 < party <= 2 else 0
    if party > 1 and level <= 6:
        max_delta = 1
    elif party > 1 and level <= 8:
        max_delta = 2
    else:
        max_delta = 3
    return max(1, target - min_target_fallback), target, max_delta


def growth_party_carry_target_plan_for_realm(
    tracked_level: int,
    party_size: int = 0,
    realm_key: str = "",
) -> tuple[int, int, int]:
    realm = str(realm_key or "").lower()
    party = int(party_size or 0)
    level = max(1, int(tracked_level or 1))
    if realm == "hib" and party == 2 and int(tracked_level or 0) <= 2:
        target = max(1, int(tracked_level or 1))
        return 1, target, 0
    if realm == "mid" and party in {2, 4} and level <= 6:
        return 4, 5, 1
    if realm == "mid" and party in {2, 4} and level == 7:
        return 5, 6, 1
    if realm == "mid" and party == 2 and level == 10:
        return 8, 9, 1
    if realm == "mid" and party >= 8 and level <= 5:
        return 3, 4, 1
    if realm == "alb" and 2 <= party <= 4 and level <= 7:
        return 5, 6, 1
    if realm == "alb" and party == 2 and level == 10:
        return 7, 8, 1
    if realm == "hib" and party == 2 and level == 10:
        return 7, 8, 1
    plan = growth_party_carry_target_plan(tracked_level, party_size)
    if realm == "hib" and party >= 8 and int(tracked_level or 0) <= 6:
        return plan[0], plan[1], max(plan[2], 3)
    return plan


def target_max_level(level: int, ideal_target: int, max_delta: int) -> int:
    if max_delta <= 0:
        return max(0, int(ideal_target))
    if int(ideal_target) < int(level):
        return min(50, max(1, int(ideal_target) + int(max_delta)))
    return min(50, max(1, int(level)) + int(max_delta))


def growth_command_max_target_level(level: int, ideal_target: int, max_delta: int, party_size: int) -> int:
    if uses_growth_party_carry_tuning(level, party_size) and int(ideal_target or 0) > int(level or 0):
        return min(50, max(1, int(ideal_target)) + max(0, int(max_delta or 0)))
    return target_max_level(level, ideal_target, max_delta)


_MIN_NON_GREY_TARGET_LEVEL_BY_PLAYER_LEVEL = (
    0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 7, 7, 7, 8, 9, 10, 11,
    12, 13, 14, 14, 14, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
    24, 25, 26, 26, 26, 26, 26, 26, 26, 27, 28, 29, 30, 31, 32,
    33, 34, 35, 36,
)


def minimum_non_grey_target_level(player_level: int) -> int:
    level = max(0, int(player_level or 0))
    if level < len(_MIN_NON_GREY_TARGET_LEVEL_BY_PLAYER_LEVEL):
        return _MIN_NON_GREY_TARGET_LEVEL_BY_PLAYER_LEVEL[level]
    return max(0, level - 14)


def enforce_reward_non_grey_target_plan(
    player_level: int,
    min_target: int,
    ideal_target: int,
    max_delta: int,
) -> tuple[int, int, int]:
    floor = minimum_non_grey_target_level(player_level)
    if floor <= 0:
        return int(min_target), int(ideal_target), int(max_delta)
    min_target = max(int(min_target), floor)
    ideal_target = max(int(ideal_target), min_target)
    return min_target, ideal_target, int(max_delta)


def minimum_growth_effective_target_level(level: int, party_size: int, realm_key: str = "") -> int:
    player_level = max(1, int(level or 1))
    non_grey_floor = minimum_non_grey_target_level(player_level)

    def floor(value: int) -> int:
        return max(int(value or 0), non_grey_floor)

    if realm_key == "alb" and int(party_size or 0) <= 1 and player_level == 8:
        return floor(6)
    if realm_key == "alb" and int(party_size or 0) <= 1 and player_level == 7:
        return floor(5)
    if realm_key == "alb" and int(party_size or 0) <= 1 and player_level == 10:
        return floor(7)
    if realm_key == "mid" and int(party_size or 0) <= 1 and player_level == 9:
        return floor(7)
    if realm_key == "mid" and int(party_size or 0) <= 1 and player_level == 10:
        return floor(7)
    if realm_key == "mid" and int(party_size or 0) <= 1 and player_level == 7:
        return floor(6)
    if realm_key == "hib" and int(party_size or 0) <= 1 and player_level == 8:
        return floor(6)
    if realm_key == "hib" and int(party_size or 0) <= 1 and player_level == 9:
        return floor(6)
    if realm_key == "hib" and int(party_size or 0) <= 1 and player_level == 10:
        return floor(7)
    if realm_key == "hib" and int(party_size or 0) <= 1 and player_level in {7, 8}:
        return floor(5)
    if int(party_size or 0) <= 2 and 5 <= player_level <= 10:
        if int(party_size or 0) == 2:
            if realm_key == "alb" and player_level == 6:
                return floor(5)
            if realm_key == "alb" and player_level == 7:
                return floor(5)
            if realm_key == "mid" and player_level == 7:
                return floor(5)
            if realm_key == "hib" and player_level == 8:
                return floor(7)
            if player_level <= 5:
                return floor(4)
            if player_level <= 9:
                return floor(max(1, player_level - 2))
            return floor(7)
        return floor(max(1, player_level - 2))
    if int(party_size or 0) <= 4 and 5 <= player_level <= 10:
        if realm_key == "mid" and player_level == 9:
            return floor(8)
        if realm_key == "hib" and player_level == 9:
            return floor(8)
        if realm_key == "hib" and player_level == 8:
            return floor(7)
        if realm_key == "alb" and player_level == 6:
            return floor(5)
        if realm_key == "mid" and player_level == 7:
            return floor(7)
        if player_level <= 5:
            return floor(4)
        if player_level <= 7:
            return floor(5)
        if player_level <= 9:
            return floor(max(1, player_level - 2))
        return floor(8)
    if int(party_size or 0) >= 8 and 5 <= player_level <= 10:
        if realm_key == "alb" and player_level == 5:
            return floor(4)
        return floor(player_level)
    if player_level <= 10:
        return non_grey_floor
    return 0
