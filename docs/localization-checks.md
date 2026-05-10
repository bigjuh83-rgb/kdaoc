# Localization Checks

Run this after server-side translation work:

```bash
tools/check-localization.sh
```

Run the same checks and then build the server:

```bash
tools/check-localization.sh --build
```

The checker validates:

- literal `LanguageMgr.GetTranslation(..., "Key")` keys used by code exist in both `GameServer/language/EN` and `GameServer/language/KR`
- EN/KR key parity warnings
- duplicate translation keys
- likely hardcoded English output strings in server message APIs
- forbidden Korean terminology such as `체질`, which should be `체력`
- long Korean strings that may need in-game UI review

Only concrete errors fail the command by default. Use `--strict-warnings` when you want warnings to fail too.

Hardcoded English candidates are warnings by default because the current server still has many GM/debug/internal strings mixed into player-facing output paths. Use `--strict-hardcoded` when you want those candidates to fail the check.
