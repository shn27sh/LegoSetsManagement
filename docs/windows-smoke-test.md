# Windows portable ZIP — manual smoke test

Use this checklist on a **real Windows 10/11** machine (or VM) after building the ZIP ([windows-packaging.md](./windows-packaging.md)). Linux CI does not run these steps.

## Before testing

- [ ] ZIP built via Phase 1 manual steps or GitHub Actions `release-windows` workflow
- [ ] Test machine has **no** requirement for Python/Node installed
- [ ] Optional: note Windows version and antivirus product

## Install and launch

- [ ] Extract ZIP to a path **without** spaces (for example `C:\LEGO-Collection-Manager`)
- [ ] Double-click **Launch LEGO Collection Manager.bat**
- [ ] Console window appears with no immediate error
- [ ] Default browser opens `http://127.0.0.1:8000/`
- [ ] Sets list page loads (may be empty collection)

## Core flows

- [ ] Navigate to **Import** and back
- [ ] Navigate to **Settings** and back
- [ ] If Rebrickable key configured in `config.env`: open a set and run sync (optional)

## Data persistence

- [ ] Add or import at least one set copy (if sample CSV available)
- [ ] Close console window (stop server)
- [ ] Relaunch `.bat` — data still present (`data\lego.db` grew on disk)

## Upgrade simulation

- [ ] Copy `data\` and `config.env` (if any) aside
- [ ] Extract a fresh ZIP to a new folder
- [ ] Copy saved `data\` into the new folder
- [ ] Launch — collection from step above still visible

## Negative checks

- [ ] Second launch while first is running: document behavior (port in use message or similar)
- [ ] SmartScreen / Defender: document if user must click through (unsigned exe)

## Sign-off

| Field | Value |
|-------|--------|
| ZIP version | |
| Build date | |
| Tester | |
| Result | PASS / FAIL |
| Notes | |
