# Always-on hosting

The map refreshes only while the news poller runs. On a laptop or desktop that stops when the machine sleeps. This guide runs the API, the poller and the console together on one small always-on server, behind HTTPS.

## Host choice

**Oracle Cloud Always Free, Ampere A1 VM.** Chosen because it is free without a time limit, never sleeps when idle, and is large enough: up to 4 Arm cores and 24 GB of memory, with 200 GB of block storage. The stack needs about 1 GB of memory at rest; the console build needs about 2 GB briefly.

Alternatives considered (as of October 2026; check current terms before relying on them):

- Fly.io no longer offers a free allowance to new accounts.
- Render and similar free web tiers sleep when idle, which stops the poller.
- Google Cloud's free e2-micro never sleeps but has 1 GB of memory, so the console build needs swap and is slow. `setup-server.sh` adds swap automatically if you use it.

Caveats: Oracle asks for a card to verify identity but does not charge Always Free resources. Arm capacity in popular regions is sometimes exhausted ("Out of capacity"); retry later or pick another availability domain. Oracle reclaims Always Free instances that look idle over 7 days (CPU, network and memory use all below 20%). This stack is light enough that it would likely count as idle, so the setup steps upgrade the account to Pay As You Go, which removes idle reclaim while Always Free resources stay free. Set a budget alert at a small amount (for example $1) to be told if anything ever bills.

## What runs

`deploy/docker-compose.server.yml` layers onto the base `docker-compose.yml`:

| Service | Role |
| --- | --- |
| `backend` | FastAPI on the internal network; applies the database migration on start |
| `poller` | `news poll`: GDELT bulk files, Wikipedia Current events and Global Voices every 15 minutes |
| `frontend` | Next.js console; reads the API server-side |
| `caddy` | Public ports 80 and 443; obtains and renews the HTTPS certificate |

`https://<site>/` serves the console. `https://<site>/api/...` serves the read-only API (for the future iPhone app), for example `/api/news`. Every service restarts automatically after a crash or reboot. The database, news cache and certificates live in Docker volumes and survive updates.

Without a domain name, the site address is the server's public IP with dashes plus `.sslip.io` (for example `203-0-113-5.sslip.io`), a free wildcard DNS service that Let's Encrypt accepts. To use your own domain later, point its DNS A record at the server, set `SITE_ADDRESS` in `deploy/.env`, and run `deploy/update.sh`.

## Set up

1. Create an Oracle Cloud account at <https://signup.cloud.oracle.com> and choose a home region close to you (it cannot be changed later). Then, under **Billing → Upgrade and Manage Payment**, upgrade to **Pay As You Go** (see caveats above), and under **Billing → Budgets** create a $1 budget with an email alert.
2. In the console: **Compute → Instances → Create instance**.
   - Image: **Canonical Ubuntu 24.04**.
   - Shape: **Ampere → VM.Standard.A1.Flex**, 2 OCPUs and 12 GB memory (within Always Free).
   - Networking: keep the default new VCN with a public IPv4 address.
   - SSH keys: download the generated private key, or paste your own public key.
3. Open the web ports: on the instance page, open the **Subnet → Default security list → Add ingress rules**, source `0.0.0.0/0`, TCP destination ports `80,443`.
4. Connect: `ssh -i <key-file> ubuntu@<public-ip>`.
5. On the server:

   ```sh
   git clone https://github.com/ParsingMAINFRAME/ThreatMon.git
   cd ThreatMon
   ./deploy/setup-server.sh
   ```

   The script installs Docker, opens ports 80 and 443 in Ubuntu's own firewall (Oracle's images block them even when the security list allows them), writes `deploy/.env`, builds the images and starts everything. It prints the site address when done. The first build takes several minutes.

## Operate

From the `ThreatMon` directory on the server:

```sh
./deploy/update.sh                      # pull main and rebuild
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.server.yml --env-file deploy/.env logs -f poller
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.server.yml --env-file deploy/.env ps
```

Each poller cycle logs one JSON line per source with its fetch state. The console's coverage panel shows each source's last successful fetch, so a stalled poller is visible on the site itself.

If the server loses power or the poller is killed, the restarted poller reclaims its own lock and resumes at once; see [news pipeline](news-pipeline.md#automatic-refresh).

## Limits

- One server, no replica or failover. If it is down, the map stops refreshing until it returns.
- No backups are configured. The news cache rebuilds itself from sources; the SQLite database holds source signals and demo scenarios.
- The poller covers the news map. USGS and CISA source signals still refresh only when `ingest` is run.
- No alerts are sent, and this is not an emergency notification service.
