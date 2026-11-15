# Airbyte: TLC files to S3

Airbyte lands the raw files in S3 with a Hive layout:

```
s3://<S3_BUCKET>/raw/yellow/year=YYYY/month=MM/yellow_tripdata/<file>.parquet
s3://<S3_BUCKET>/raw/zones/taxi_zone_lookup/<file>.csv
```

The Airbyte configuration is versioned in [`connections/`](connections/), one YAML per dataset.
Secrets are never stored there: the `{env.NAME}` placeholders are filled from `.env` when the
pipeline calls the Airbyte API. **Nothing is configured by hand in the Airbyte UI.**

## 1. Install Airbyte locally (once per machine)

Airbyte runs on a small Kubernetes cluster inside Docker. On an 8 GB laptop, stop other heavy
containers first and use the low-resource mode:

```bash
curl -LsfS https://get.airbyte.com | bash -   # or download abctl from the Airbyte releases page
abctl local install --low-resource-mode
abctl local credentials                      # prints client-id / client-secret for the API
```

By default the UI and API are at http://localhost:8000. Copy the workspace id from the UI URL:
`/workspaces/<UUID>/...`.

## 2. Fill `.env`

```
AIRBYTE_API_URL=http://localhost:8000/api/public/v1
AIRBYTE_CLIENT_ID=...
AIRBYTE_CLIENT_SECRET=...
AIRBYTE_WORKSPACE_ID=...
S3_BUCKET=...
AIRBYTE_S3_ACCESS_KEY_ID=...        # IAM user nyc-taxi-pipeline (S3 permissions on the bucket only)
AIRBYTE_S3_SECRET_ACCESS_KEY=...
```

The S3 destination cannot read an AWS profile, so it needs access keys. The pipeline itself
(listing, downloading and verifying) uses the AWS profile in `AWS_PROFILE`.

## 3. Everything else is automatic

`make all` (or `make airbyte-sync`) creates whatever Airbyte objects are missing the first time
they are needed: a source, an S3 destination and a manual connection (full refresh, overwrite)
for each dataset. The setup is **idempotent**:

- An object that already exists with the versioned name is reused, never duplicated.
- Every id is saved to `airbyte/state/ids.json` (gitignored) as soon as it is known, so an
  interrupted setup just continues on the next run.
- Creating a connection makes Airbyte discover the source schema. The File source downloads the
  whole month (about 60 MB) to do it, so the wrapper waits up to 15 minutes. Timeouts and 5xx
  answers are retried after 1 s, 2 s and 4 s, and every retry first looks for the object it was
  creating.

`make airbyte-setup` runs the same setup ahead of time. It is optional.

## 4. What `make airbyte-sync MES=2025-01` does

For each dataset and month (the month and the same month of the previous year):

1. **Skip if current.** If the last successful `ingestion_log` entries still match S3 (size and
   ETag) and the local mirror (SHA-256), nothing is synced and an entry with `action=skipped` is
   logged. A month ingested earlier without S3 (offline mode) is synced again.
2. **Parametrize.** The source URL (`yellow_tripdata_{mes}.parquet`) and the destination path
   (`year={year}/month={month}`) of the versioned YAML are sent to the API.
3. **Sync with retries.** If the job fails, the wrapper retries 3 times, waiting 1 s, 2 s and 4 s.
   If it still fails, it logs `status=error` and exits with code 1.
4. **Verify.** Objects older than this sync under the month prefix are removed (overwrite safety
   net). Each landed object is downloaded to `DATA_DIR/raw/...` computing SHA-256, its Parquet row
   count is compared with the job's `rowsSynced`, and a row is logged with file, URL, bytes,
   SHA-256, rows, ETag, job id, timestamp and status.

## Why the monthly files use `INGEST_MODE=hybrid`

Tested on 2026-11-14 with Airbyte's File source (abctl), syncing the monthly yellow Parquet.

1. **VM memory.** The source loads the whole month into pandas, about 2.5 GB for 3.5M rows. With
   WSL2's default 7.6 GB the Docker VM ran out of memory, so the VM was raised to 12 GB.
2. **Pod memory.** Airbyte limits each job container to 4Gi, and the replication pod was
   `OOMKilled`. The versioned connection now asks for 7Gi (`resources` in
   `connections/yellow_tripdata.yaml`), and with that there is no more OOM.
3. **Connector bug.** The File source then fails on every attempt with
   `Object of type Timestamp is not JSON serializable`, with 0 records emitted. It cannot serialize
   the pandas `Timestamp` values of the Parquet's datetime columns. This does not depend on
   resources. The zone lookup is a CSV without datetimes and syncs fine.

So `INGEST_MODE=hybrid` is the working configuration:
- Airbyte syncs the zone lookup.
- The monthly trip files are streamed from the TLC CDN straight to the same S3 path. Memory stays
  constant, and the landed object is the original, unmodified file with the same SHA-256,
  `ingestion_log`, idempotency and retries.

`INGEST_MODE=airbyte` stays available for a future connector version.

## Memory settings for `INGEST_MODE=airbyte`

Airbyte's File source loads the whole Parquet into pandas. For one month (3.5M rows) the
`source-file` process reached 2.5 GB. With WSL2's default limit (50% of RAM, 7.6 GB on a 16 GB
laptop), next to the Airbyte platform (about 4.5 GB), the Docker VM ran out of memory and the kernel
killed the job (OOM). The zone lookup syncs fine either way.

- **Windows (WSL2):** create `%USERPROFILE%\.wslconfig` with the content below, then run
  `wsl --shutdown` and restart Docker Desktop. `docker info` should then report about 12 GB.

  ```
  [wsl2]
  memory=12GB
  swap=8GB
  ```

- **Linux:** Docker uses the host memory directly, so no setting is needed.
- **macOS:** Docker Desktop > Settings > Resources > Memory.

On machines with 8 GB or less, use `INGEST_MODE=hybrid`. It keeps Airbyte for the zone lookup and
streams the monthly trip files from the TLC CDN straight to the same S3 path. Memory stays constant,
and the landed object is the original, unmodified file with the same SHA-256, `ingestion_log`,
idempotency and retries.

## Troubleshooting: the connection is never created

Symptom: `POST /connections` answers HTTP 502 after 5 minutes again and again, and no
`source-file-discover-*` pod ever starts (`kubectl get pods -n airbyte-abctl` inside the
`airbyte-abctl-control-plane` container).

Cause seen after upgrading abctl: the workspace belongs to one dataplane group, but the workload
launcher registered itself in another one. Discover jobs are queued for a group that no launcher
polls, so they stay `pending` forever. To check, compare `workspace.dataplane_group_id` with the
group of the launcher's dataplane (the launcher log says `Initalizing ApiQueuePoller with <group>`).

Fix:
1. Terminate the stuck `discover_*` Temporal workflows and mark their workloads as cancelled.
2. Move the launcher's dataplane to the workspace's group
   (`update dataplane set dataplane_group_id = '<workspace group>' where id = '<launcher dataplane>'`).
3. Restart `airbyte-abctl-workload-launcher`.

The pipeline then creates the connections on its own.

## Notes

- The File source reads the Parquet with pandas, so Airbyte may change some types. For example,
  `passenger_count` becomes double because of NULLs, and timestamps may arrive as strings. The schema
  step reports those differences and casts them to the contract types. The `_airbyte_*` metadata
  columns are ignored.
- Fallback without Airbyte: `INGEST_MODE=direct` downloads the same files from the TLC CDN with
  the same retries and log, and uploads them unmodified to the same S3 path when `S3_BUCKET` is set.
