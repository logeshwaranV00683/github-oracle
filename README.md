# Oracle A1.Flex Auto-Retry

Automatically tries to create Oracle Cloud A1.Flex instance every 10 minutes via GitHub Actions — no PC needed!

## Setup (5 minutes)

### Step 1 — Add GitHub Secrets

Go to your GitHub repo → **Settings → Secrets and Variables → Actions → New repository secret**

Add these 7 secrets:

| Secret Name | Where to get it |
|---|---|
| `USER_OCID` | Oracle Console → Profile icon → My Profile → OCID |
| `FINGERPRINT` | Profile → My Profile → API Keys → Add API Key → copy fingerprint from preview |
| `OCI_PRIVATE_KEY` | The downloaded `.pem` file content — open in Notepad, copy ALL text |
| `TENANCY_OCID` | Profile → click Tenancy name → copy OCID |
| `COMPARTMENT_ID` | Identity & Security → Compartments → root → copy OCID |
| `SUBNET_ID` | Networking → VCN → core compass → corecompass-subnet → copy OCID |
| `IMAGE_ID` | Compute → Create Instance → Change Image → Ubuntu 22.04 → aarch64 → copy OCID |
| `SSH_PUBLIC_KEY` | Your id_rsa.pub file content (entire line starting with ssh-rsa...) |

### Step 2 — Push to GitHub

```bash
git init
git add .
git commit -m "Oracle auto-retry"
git remote add origin https://github.com/YOUR_USERNAME/oracle-retry.git
git push -u origin main
```

### Step 3 — Enable Actions

GitHub repo → **Actions tab** → Enable workflows if prompted

### Step 4 — Watch it run

GitHub repo → **Actions tab** → See every run

When instance is created you'll see **🎉 SUCCESS** in the logs!

## How it works

- Runs every 10 minutes automatically (via GitHub cron)
- Tries all 3 Availability Domains per run
- Stops automatically when instance is created
- Completely free — GitHub Actions free tier = 2000 min/month

## To Stop (after instance is created)

GitHub repo → **Actions → oracle-retry.yml → Disable workflow**
