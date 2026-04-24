# Oracle A1.Flex Auto-Retry via GitHub Actions

PC off aanalum every 10 minutes automatically try pannும்!

---

## Setup — 3 Steps Only

### Step 1 — GitHub repo create pannu

```
github.com → New repository → Name: oracle-retry → Public → Create
```

### Step 2 — These files push pannu

```bash
git init
git add .
git commit -m "Oracle auto-retry"
git remote add origin https://github.com/YOUR_USERNAME/oracle-retry.git
git push -u origin main
```

### Step 3 — GitHub Secrets add pannu

**Repo → Settings → Secrets and Variables → Actions → New repository secret**

Add these 6 secrets exactly:

| Secret Name | Value |
|---|---|
| `OCI_USER` | `ocid1.user.oc1..aaaaaaaaphruty4hazbop2vyof6titcstvldwcw6p6fwvuwgnl63kesluroa` |
| `OCI_FINGERPRINT` | `17:95:df:63:d8:6d:b5:9c:e3:1c:de:af:94:d5:74:9b` |
| `OCI_TENANCY` | `ocid1.tenancy.oc1..aaaaaaaabi6jpiihh24imbmlhbe7abqzxikp4gn3lki2txscr7h7vxsayq3a` |
| `OCI_PRIVATE_KEY` | Your .pem file — open in Notepad, copy ENTIRE content including -----BEGIN----- and -----END----- lines |
| `COMPARTMENT_ID` | Oracle Console → Identity → Compartments → root → copy OCID |
| `SUBNET_ID` | Networking → VCN → core compass → corecompass-subnet → copy OCID |
| `SSH_PUBLIC_KEY` | Contents of id_rsa.pub file (run: cat ~/.ssh/id_rsa.pub) |

### Done!

GitHub Actions → oracle-retry.yml → runs every 10 minutes.

When SUCCESS → check Actions logs for instance details.

Then disable the workflow: Actions → oracle-retry.yml → Disable workflow
