# Tailscale exit node on the QNAP (residential egress for car-hunt CI)

The car-hunt workflow routes runner egress through a home exit node when the
`TS_OAUTH_CLIENT_ID` / `TS_OAUTH_SECRET` repo secrets are set, so WebFetch and
the Playwright browser leave from a residential IP instead of GitHub's
datacenter ranges (which AutoTrader/CarGurus bot walls block). Without the
secrets, the Tailscale steps no-op and the workflow runs with datacenter
egress.

## 1. Tailscale admin console (one-time)

1. Create a tailnet at https://login.tailscale.com (free Personal plan is fine).
2. **Access Controls** → add a tag for ephemeral CI nodes:
   ```jsonc
   "tagOwners": {
     "tag:ci": ["autogroup:admin"]
   }
   ```
   (With the default allow-all ACL, tagged nodes may use exit nodes; if you
   later tighten ACLs, `tag:ci` needs a rule reaching `autogroup:internet`.)
3. **Settings → OAuth clients** → Generate OAuth client with the
   **Auth Keys** write scope, tag `tag:ci`. Save the client ID and secret.

## 2. QNAP Container Station (TS-451+, QTS 5.2.x)

Create an application (docker-compose) with:

```yaml
services:
  tailscale-exit:
    image: tailscale/tailscale:stable
    container_name: tailscale-exit
    hostname: qnap-exit            # must match --exit-node in the workflow
    network_mode: host
    cap_add:
      - NET_ADMIN
      - NET_RAW
    devices:
      - /dev/net/tun:/dev/net/tun
    volumes:
      - /share/Container/tailscale-state:/var/lib/tailscale
    environment:
      - TS_AUTHKEY=tskey-auth-REPLACE-ME   # one-time auth key, see below
      - TS_EXTRA_ARGS=--advertise-exit-node
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_USERSPACE=false
    restart: unless-stopped
```

- `TS_AUTHKEY`: admin console → **Settings → Keys** → Generate auth key
  (reusable off, expiry fine — state persists in the volume after first auth,
  and you can remove the env var afterwards).
- Create the `/share/Container/tailscale-state` folder first (File Station).

After the container starts: admin console → **Machines** → `qnap-exit` →
**Edit route settings** → enable **Use as exit node**. Optionally disable key
expiry for the machine so it never drops off.

## 3. Repo secrets

```
gh secret set TS_OAUTH_CLIENT_ID -R don-petry/don-petry
gh secret set TS_OAUTH_SECRET    -R don-petry/don-petry
```

Next workflow run will show `egress IP: <github> -> <home>` in the
"Route egress through home exit node" step. That step fails loudly if the
exit node is unreachable or unapproved — fix the NAS or remove the secrets to
fall back to datacenter egress.

## Notes / gotchas

- The CI node joins as ephemeral (`tag:ci` via OAuth) and disappears after
  each run — no machine buildup in the admin console.
- ALL runner egress rides the exit node during the run (GitHub API, Claude
  API, npm). Bandwidth is modest (a few hundred MB per run worst case);
  chromium downloads happen *before* the exit-node switch by step order.
- WebSearch results are fetched by Anthropic server-side and are unaffected.
- If the home connection is down, runs fail at the routing step rather than
  silently running with datacenter egress.
