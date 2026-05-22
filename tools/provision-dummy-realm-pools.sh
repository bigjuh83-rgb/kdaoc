#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MYSQL_BIN="${MYSQL_BIN:-/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb}"
DB_PASSWORD="${DB_PASSWORD:-$(
python3 - <<'PY'
import re
from pathlib import Path

config = Path("CoreServer/config/serverconfig.xml").read_text(encoding="utf-8")
match = re.search(r"Password=([^;]+)", config)
print(match.group(1) if match else "opendaoc-local")
PY
)}"

REPLACE_ARGS=()
if [[ "${OPENDAOC_REALM_POOL_REPLACE:-0}" == "1" || "${OPENDAOC_REALM_POOL_REPLACE:-0}" == "true" ]]; then
  REPLACE_ARGS+=(--replace)
fi

COMMON_ARGS=(
  --mysql-bin "$MYSQL_BIN"
  --db-password "$DB_PASSWORD"
  --template-account dummy040
  --template-character Dummy040
  --start 1
  --count "${OPENDAOC_REALM_POOL_COUNT:-40}"
  --password "${OPENDAOC_DUMMY_PASSWORD:-dummy-pass}"
  --slot-index 0
  "${REPLACE_ARGS[@]}"
)

POOL_COUNT="${OPENDAOC_REALM_POOL_COUNT:-40}"

python3 tools/provision-dummy-accounts.py "${COMMON_ARGS[@]}" \
  --prefix albtest \
  --character-prefix Albtest \
  --realm 1 \
  --class-cycle "1|2|11|10|6|6|7|5|1|2|11|4|6|10|13|8" \
  --race-cycle "1|3|1|3|3|3|1|1|1|3|1|1|3|3|2|2" \
  --spec-cycle "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13||Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1||Slash|50;Thrust|1;Crush|1;Dual Wield|50;Parry|28||Staff|39;Enhancement|45;Rejuvenation|30;Parry|18||Smite|1;Rejuvenation|40;Enhancement|36||Smite|1;Rejuvenation|40;Enhancement|36||Fire Magic|50;Earth Magic|15;Cold Magic|10||Earth Magic|45;Cold Magic|25;Wind Magic|8||Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13||Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1||Slash|50;Thrust|1;Crush|1;Dual Wield|50;Parry|28||Instruments|44;Slash|39;Stealth|25||Smite|1;Rejuvenation|40;Enhancement|36||Staff|39;Enhancement|45;Rejuvenation|30;Parry|18||Matter Magic|46;Body Magic|28;Spirit Magic|4||Body Magic|45;Mind Magic|29;Matter Magic|4" \
  --csv "tools/dummy-accounts-albion-${POOL_COUNT}.csv"

python3 tools/provision-dummy-accounts.py "${COMMON_ARGS[@]}" \
  --prefix midtest \
  --character-prefix Midtest \
  --realm 2 \
  --class-cycle "22|22|31|24|26|26|28|29" \
  --race-cycle "5|7|6|5|7|7|8|5" \
  --spec-cycle "Hammer|50;Shields|42;Parry|39;Sword|1;Axe|1;Thrown Weapons|1||Sword|50;Shields|42;Parry|39;Hammer|1;Axe|1;Thrown Weapons|1||Axe|50;Left Axe|50;Parry|28;Sword|1;Hammer|1||Sword|44;Battlesongs|46;Parry|21;Hammer|1;Axe|1||Mending|40;Augmentation|36;Pacification|1||Mending|40;Augmentation|36;Pacification|1||Augmentation|40;Mending|36;Subterranean|1||Runecarving|50;Darkness|15;Suppression|10" \
  --csv "tools/dummy-accounts-midgard-${POOL_COUNT}.csv"

python3 tools/provision-dummy-accounts.py "${COMMON_ARGS[@]}" \
  --prefix hibtest \
  --character-prefix Hibtest \
  --realm 3 \
  --class-cycle "44|43|45|48|47|47|40|41" \
  --race-cycle "9|9|9|9|9|9|11|11" \
  --spec-cycle "Blades|50;Shields|42;Parry|39;Large Weapons|1;Celtic Spear|1||Blades|50;Celtic Dual|50;Parry|28;Shields|1||Large Weapons|50;Valor|40;Parry|23;Shields|1;Blades|1||Music|43;Nurture|37;Regrowth|33;Blades|1||Regrowth|40;Nurture|36;Nature|1||Regrowth|40;Nurture|36;Nature|1||Light|50;Mana|15;Void|10||Mana|50;Enchantments|20;Light|1" \
  --csv "tools/dummy-accounts-hibernia-${POOL_COUNT}.csv"

POOL_CSVS=(
  "tools/dummy-accounts-albion-${POOL_COUNT}.csv"
  "tools/dummy-accounts-midgard-${POOL_COUNT}.csv"
  "tools/dummy-accounts-hibernia-${POOL_COUNT}.csv"
)

python3 tools/equip-dummy-boss-gear.py \
  --mysql-bin "$MYSQL_BIN" \
  --db-password "$DB_PASSWORD" \
  "${POOL_CSVS[@]}"

python3 tools/validate-dummy-50-setup.py \
  --mysql-bin "$MYSQL_BIN" \
  --db-password "$DB_PASSWORD" \
  "${POOL_CSVS[@]}"

echo "realm dummy pools ready:"
echo "  Albion   tools/dummy-accounts-albion-${POOL_COUNT}.csv"
echo "  Midgard  tools/dummy-accounts-midgard-${POOL_COUNT}.csv"
echo "  Hibernia tools/dummy-accounts-hibernia-${POOL_COUNT}.csv"
echo "  Boss gear and level-50 DB validation completed"
