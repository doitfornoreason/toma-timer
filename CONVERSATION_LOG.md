# Conversation Log

## [2026-07-19] Todo list + Settings as tab + Ubuntu notes
- did:
  - Added todo list feature: `todos` table in DB, CRUD functions, UI in Timer tab (scrollable, checkboxes with strikethrough, remove completed, add new)
  - Bumped todo label font 13→14
  - Added "Delete All Records" button in Settings with confirmation dialog + `clear_all_data()` in DB
  - Converted Settings from `CTkToplevel` popup → scrollable tab (removed `SettingsDialog` class entirely)
  - Fixed `_apply_settings` to use `update()` instead of replace (was losing keys)
  - Created `USAGE.md` with cross-platform & Ubuntu setup notes
- decided:
  - Settings tab applies changes immediately, no Apply/Cancel
  - Settings uses `CTkScrollableFrame` for scrollability
- open:
  - PyInstaller single binary packaging
  - .desktop file for app menu
  - Real desktop tray testing (Wayland no StatusNotifierItem host)
- issues:
  - (none)