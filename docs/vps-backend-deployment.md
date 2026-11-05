# Update the Langchain backend on the Hostinger VPS

This guide updates the existing Docker Compose backend using source uploaded from Windows. The VPS source folder is not a Git checkout, so this procedure does not use `git pull`.

The workflow is: package local source → upload → back up the VPS → extract into the backend folder → build → replace the backend container → verify its files and behavior.

## Deployment details

| Item | Value |
| --- | --- |
| VPS hostname | `srv2104288.hstgr.cloud` |
| VPS IP | `76.13.210.218` |
| SSH user | `root` |
| Local backend source | `C:\Users\AIX - Production\Documents\Langchain` |
| VPS Compose folder | `/opt/aida-stack` |
| VPS backend source | `/opt/aida-stack/backend` |
| Dockerfile | `/opt/aida-stack/Dockerfile` |
| Compose file for backend updates | `/opt/aida-stack/compose.yaml` |
| Compose service | `backend` |
| Running container | `aida-stack-backend-1` |
| Application folder inside container | `/srv/app` |
| Backend host endpoint | `http://127.0.0.1:8000` on the VPS |

**Extract backend archives into `/opt/aida-stack/backend`, not `/opt/aida-stack`.** The Dockerfile uses `COPY backend/app ./app`, `COPY backend/prompts ./prompts`, and `COPY backend/static ./static`. Updating `/opt/aida-stack/app` does not update the files used by this build.

This procedure updates only the backend. It preserves the frontend, server environment files, Compose configuration, Dockerfile, and Qdrant volumes. Backend requests may briefly fail when its container is replaced.

## 1. Package the local backend

**Where: your computer — Windows PowerShell.**

```powershell
cd "C:\Users\AIX - Production\Documents\Langchain"
```

`cd` selects the local project folder. The archive paths below are relative to this directory.

```powershell
tar -czf "$env:TEMP\aida-backend-update.tar.gz" app prompts static pyproject.toml uv.lock README.md
$LASTEXITCODE
```

| Part | Explanation |
| --- | --- |
| `tar` | Packages source files into an archive |
| `-c` | Creates an archive |
| `-z` | Compresses it using gzip |
| `-f` | Specifies the archive filename |
| `$env:TEMP` | Your Windows temporary folder |
| `app prompts static` | Application code, model prompts, and bundled web assets |
| `pyproject.toml uv.lock` | Dependency declarations and locked dependency versions |
| `README.md` | Required by the existing Dockerfile's dependency copy step |
| `$LASTEXITCODE` | Shows the preceding command's exit code; `0` means success |

The explicit file list omits `.env`, Git metadata, your Windows virtual environment, tests, local Qdrant data, and server deployment configuration. Python caches inside `app` may be included but are not source; the verification step excludes them.

```powershell
Get-Item "$env:TEMP\aida-backend-update.tar.gz" | Select-Object FullName, Length, LastWriteTime
tar -tzf "$env:TEMP\aida-backend-update.tar.gz"
```

`Get-Item` confirms the archive exists and shows its size and timestamp. `tar -t` lists its contents without extracting. Confirm the expected source paths appear and that `.env` is absent. Archive creation normally succeeds silently.

## 2. Upload the archive

**Where: your computer — Windows PowerShell.**

```powershell
scp "$env:TEMP\aida-backend-update.tar.gz" root@76.13.210.218:/root/
```

`scp` transfers the local archive to `/root/aida-backend-update.tar.gz` on the VPS over SSH. Enter the VPS root password, not the Hostinger account password or Qdrant API key. Password characters are not displayed while typing or pasting. Wait for the transfer to finish.

## 3. Open a VPS terminal and inspect the deployment

**Where: Hostinger hPanel → your VPS → browser terminal.**

Alternatively, connect from your computer's PowerShell:

```powershell
ssh root@76.13.210.218
```

After SSH login, the same window is a **VPS terminal**. Commands below run on Ubuntu, not your Windows computer.

**Where: VPS terminal.**

```bash
cd /opt/aida-stack
pwd
ls -lh /root/aida-backend-update.tar.gz
docker compose -f compose.yaml ps -a backend
```

| Command | Explanation |
| --- | --- |
| `cd /opt/aida-stack` | Opens the deployment folder |
| `pwd` | Confirms the current folder is `/opt/aida-stack` |
| `ls -lh ...` | Confirms the uploaded archive exists and shows its size |
| `docker compose -f compose.yaml ps -a backend` | Shows the existing backend container, including if it is stopped |

If the archive is missing, finish the Windows upload before proceeding.

## 4. Back up the current backend

**Where: VPS terminal, in `/opt/aida-stack`.**

```bash
docker image tag "$(docker inspect aida-stack-backend-1 --format '{{.Image}}')" aida-backend:before-update
```

`docker inspect` gets the image ID used by the running backend. `$(...)` substitutes that value into `docker image tag`. The backup tag keeps a reference to the current image for rollback without restarting it. Each deployment replaces this tag with the image running at that time. Do not prune this backup image before verifying the release.

```bash
tar -czf "/root/aida-backend-source-backup-$(date +%Y%m%d-%H%M%S).tar.gz" backend/app backend/prompts backend/static backend/pyproject.toml backend/uv.lock backend/README.md
```

This backs up the source files about to be updated. `date` gives the backup a unique timestamp. It does not back up Qdrant data or restore the running image automatically. The existing deployment configuration is not changed by this procedure.

Stop if either backup command reports an error.

## 5. Extract into the correct source folder

**Where: VPS terminal.**

```bash
tar -xzf /root/aida-backend-update.tar.gz -C /opt/aida-stack/backend
```

`-x` extracts, `-z` reads gzip compression, `-f` identifies the archive, and `-C` selects the destination. The resulting paths must include `/opt/aida-stack/backend/app` and `/opt/aida-stack/backend/prompts`.

Matching files are overwritten. Files deleted locally remain on the VPS after extraction. For releases that remove or rename files, review and remove obsolete server files individually; do not delete the backend folder or any volumes blindly.

```bash
ls -l backend/app/features/ad_review/audit.py backend/app/features/ad_review/service.py backend/prompts/judge.md
cat Dockerfile
```

`ls` confirms important files exist in the correct folder. `cat Dockerfile` shows the actual build instructions. Confirm its `COPY` paths still use `backend/` as described above. Uploaded files alone do not change the running container.

## 6. Build the backend image

**Where: VPS terminal, in `/opt/aida-stack`.**

```bash
docker compose -f compose.yaml build backend
```

`-f compose.yaml` selects the existing backend deployment configuration. `build backend` builds only the backend image, installing dependencies from `uv.lock` and copying source from `backend/`. Docker's normal cache checks source changes; `--no-cache` is not required for routine updates.

Wait for successful completion. A failed build does not replace the currently running backend. Resolve build errors before proceeding.

The existing Dockerfile copies only the paths listed in step 1. If a future feature requires a new top-level folder such as `assets/`, update the packaging list and Dockerfile together after checking the feature's requirements.

## 7. Replace the backend container

**Where: VPS terminal. Run only after the build succeeds.**

```bash
docker compose -f compose.yaml up -d --no-deps --force-recreate backend
```

| Part | Explanation |
| --- | --- |
| `up` | Creates or updates the selected service |
| `-d` | Runs it in the background |
| `--no-deps` | Does not start or recreate dependency services |
| `--force-recreate` | Replaces the backend container even if Compose considers it unchanged |
| `backend` | Selects only the backend service |

The replacement should retain the name `aida-stack-backend-1`. Existing requests can be interrupted; run the update when no important review is in progress. The frontend and Qdrant stay running.

**Do not run `docker compose down -v`.** That removes named volumes and can delete stored guideline data.

## 8. Check startup and readiness

**Where: VPS terminal.**

```bash
docker compose -f compose.yaml ps backend
docker compose -f compose.yaml logs --tail=80 backend
curl -sS http://127.0.0.1:8000/api/status
```

`ps` checks container state. `logs --tail=80` shows recent startup output. `curl -sS` requests backend status while still displaying connection errors. Inspect dependency booleans, missing models, and passage counts; HTTP 200 alone does not prove the AI pipeline is ready.

For this deployment the expected ASC collection count was 876 after its snapshot restore. Future document changes may legitimately change that number. A source deployment does not update Qdrant collections.

The API is bound to the VPS loopback address. A public `http://76.13.210.218:8000/` link may not work; use the existing website or the VPS-local URL above.

## 9. Verify all deployed source files

Compare the running container, not just files in the VPS source folder. Normalize Windows/Linux line endings before hashing.

### Create the local manifest

**Where: your computer — PowerShell, in the Langchain folder.**

```powershell
@'
import hashlib, json
from pathlib import Path
root = Path.cwd()
paths = [p for folder in ('app', 'prompts', 'static')
         for p in (root / folder).rglob('*')
         if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
paths += [root / f for f in ('pyproject.toml', 'uv.lock', 'README.md')]
files = {}
for p in sorted(paths):
    data = p.read_bytes()
    try:
        data = data.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').encode()
    except UnicodeDecodeError:
        pass
    files[p.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
Path('local-backend-manifest.json').write_text(json.dumps(files, indent=2), encoding='utf-8')
print('Local files:', len(files))
'@ | .\.venv\Scripts\python.exe -
```

The Python code reads each deployed source file and calculates a SHA-256 fingerprint. Text encoding markers and line endings are normalized; binary files are hashed unchanged. It writes a local comparison artifact and does not modify application source or read environment secrets.

### Create the running VPS manifest

**Where: VPS terminal.**

```bash
docker exec -i aida-stack-backend-1 python - > /root/aida-vps-manifest.json <<'PY'
import hashlib, json
from pathlib import Path
root = Path('/srv/app')
paths = [p for folder in ('app', 'prompts', 'static')
         for p in (root / folder).rglob('*')
         if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
paths += [root / f for f in ('pyproject.toml', 'uv.lock', 'README.md')]
files = {}
for p in sorted(paths):
    data = p.read_bytes()
    try:
        data = data.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').encode()
    except UnicodeDecodeError:
        pass
    files[p.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
print(json.dumps(files, indent=2))
PY
```

`docker exec -i` runs Python inside the live backend and accepts the script on standard input. `<<'PY'` supplies literal script text. `>` saves its JSON output on the VPS host. This reads running source without modifying it.

### Download and compare

**Where: your computer — PowerShell, in the Langchain folder.**

```powershell
scp root@76.13.210.218:/root/aida-vps-manifest.json .\vps-backend-manifest.json
```

This downloads the running-container fingerprints.

```powershell
@'
import json
from pathlib import Path
local = json.loads(Path('local-backend-manifest.json').read_text(encoding='utf-8-sig'))
vps = json.loads(Path('vps-backend-manifest.json').read_text(encoding='utf-8-sig'))
print('Matching:', sum(local[k] == vps[k] for k in local.keys() & vps.keys()))
print('Changed:', sorted(k for k in local.keys() & vps.keys() if local[k] != vps[k]))
print('Missing on VPS:', sorted(local.keys() - vps.keys()))
print('Extra on VPS:', sorted(vps.keys() - local.keys()))
'@ | .\.venv\Scripts\python.exe -
```

The comparison reports matching files and every changed, missing, or extra path. A previous verified deployment matched all 72 checked files; the total may change as the project grows. Matching files does not verify environment settings, installed packages, model versions, or Qdrant content.

## 10. Test the actual website

**Where: your computer — browser.**

Open the existing AIDA website. Start a new conversation and verify:

1. A text message receives a complete response.
2. The same original image and message can be reviewed successfully.
3. Findings, approval explanations, and review notes appear consistently.
4. PDF download works.
5. No new request errors occur.

A build or matching source manifest is not a substitute for a live behavior check. Identical source also does not guarantee identical generated wording. Compare environment settings, the actual model versions, original image bytes, retrieved evidence, and raw stage outputs when investigating judgment differences.

## Environment settings

Local `.env` is not part of the upload. The backend uses `/opt/aida-stack/.env` and the `backend.environment` values in `compose.yaml`; Compose environment entries override matching values from its `env_file`. Settings absent from the process environment use defaults in `app/core/config.py`, so updating that file can change those defaults.

**Where: VPS terminal.**

```bash
docker compose -f /opt/aida-stack/compose.yaml exec backend printenv VISION_NUM_CTX
```

This reads one effective container environment setting without printing API keys. To change it, edit the backend's `VISION_NUM_CTX` entry in `/opt/aida-stack/compose.yaml`, then recreate the backend using step 7. An environment-only change needs container recreation, not an image rebuild.

The VPS has used remote Ollama endpoints `http://100.87.84.50:11434` for generation and `http://100.87.84.50:11435` for embeddings. Preserve the existing working configuration unless deliberately changing the model server. Local model downloads and local Qdrant data are not deployed by this procedure.

## Roll back a failed release

**Where: VPS terminal.**

Create a rollback override that selects the image saved in step 4:

```bash
cd /opt/aida-stack
nano backend.rollback.yaml
```

`nano` opens the override file. Paste:

```yaml
services:
  backend:
    image: aida-backend:before-update
```

Save with **Ctrl+O → Enter → Ctrl+X**, then run:

```bash
docker compose -f compose.yaml -f backend.rollback.yaml up -d --no-build --no-deps --force-recreate backend
```

The second Compose file overrides the image selection. `--no-build` avoids rebuilding the problematic source. This restores the previous image using current service configuration; it does not restore source files, environment settings, or database state. Repeat startup and website checks.

For the next corrected release, use the normal command with only `-f compose.yaml`. Restore selected source files from the timestamped backup if needed; extracting a source backup alone does not change the running container.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `tar` says archive does not exist | Create and upload it from Windows before extracting on VPS |
| SSH password appears not to type | Password input is hidden; use the VPS root password |
| Source changed but container still has old behavior | Confirm extraction destination is `/opt/aida-stack/backend`, then build and recreate |
| Build succeeds but expected files are missing | Inspect Dockerfile `COPY` paths and the running-container manifest |
| Container restarts repeatedly | Inspect backend logs before trying further redeployments |
| Responses still differ from local | Compare effective settings, model versions, dependencies, Qdrant content, and stage outputs |
| Public port 8000 link fails | Existing configuration binds it to VPS loopback; test from VPS or through the existing website |
| Deleted files remain on VPS | Archive extraction does not remove old files; review obsolete paths individually |

## Later updates

Repeat steps 1–10 using the local source you intend to release. Always keep the source archive separate from server configuration, extract into `backend/`, and verify files inside the running container after replacement.
