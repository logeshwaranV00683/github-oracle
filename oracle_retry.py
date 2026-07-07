import oci
import os
import sys
import time
from datetime import datetime

# ================================================================
# All values come from GitHub Secrets — nothing hardcoded
# ================================================================

config = {
    "user":        os.environ["OCI_USER"],
    "fingerprint": os.environ["OCI_FINGERPRINT"],
    "tenancy":     os.environ["OCI_TENANCY"],
    "region":      "ap-hyderabad-1",
    "key_file":    os.path.expanduser("~/.oci/oci_api_key.pem"),
}

COMPARTMENT_ID = os.environ["COMPARTMENT_ID"]
SUBNET_ID      = os.environ["SUBNET_ID"]
SSH_PUBLIC_KEY = os.environ["SSH_PUBLIC_KEY"]

DISPLAY_NAME = "corecompass-prod"

# Shape configs to try, in order, per attempt.
# NOTE: Oracle cut the Always Free A1.Flex allowance from 4 OCPU/24GB to
# 2 OCPU/12GB total, effective June 15, 2026 (undocumented change).
# Requesting 4/24 on a free-tier account will now fail even with capacity
# available, so we lead with the real current limit and fall back smaller
# in case partial capacity is all that's free.
SHAPE_CONFIGS = [
    {"ocpus": 2, "memory_in_gbs": 12},
    {"ocpus": 1, "memory_in_gbs": 6},
]

# ================================================================
# REALITY CHECK — never guess from error text, always verify via API
# ================================================================

ACTIVE_STATES = ["PROVISIONING", "RUNNING", "STARTING", "STOPPING", "STOPPED"]

def find_existing_instance(compute):
    """Return the instance object if one already exists in an active state, else None."""
    try:
        instances = oci.pagination.list_call_get_all_results(
            compute.list_instances,
            COMPARTMENT_ID,
            display_name=DISPLAY_NAME,
        ).data
        for inst in instances:
            if inst.lifecycle_state in ACTIVE_STATES:
                return inst
        return None
    except Exception as e:
        print(f"⚠️  Could not check existing instances: {e}")
        return None

# ================================================================
# AUTO-DETECT — image OCID and ADs fetched automatically
# ================================================================

def get_latest_ubuntu_arm_image(compute):
    print("🔍 Finding latest Ubuntu 22.04 ARM image...", flush=True)
    try:
        images = oci.pagination.list_call_get_all_results(
            compute.list_images,
            COMPARTMENT_ID,
            operating_system="Canonical Ubuntu",
            operating_system_version="22.04",
            shape="VM.Standard.A1.Flex",
            sort_by="TIMECREATED",
            sort_order="DESC",
        ).data

        arm_images = [
            img for img in images
            if "aarch64" in img.display_name.lower()
            and img.lifecycle_state == "AVAILABLE"
        ]

        if arm_images:
            img = arm_images[0]
            print(f"   ✅ {img.display_name}")
            return img.id
        else:
            print("   ❌ No ARM image found!")
            return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def get_availability_domains(identity):
    try:
        ads = identity.list_availability_domains(COMPARTMENT_ID).data
        names = [ad.name for ad in ads]
        print(f"📍 ADs: {names}")
        return names
    except Exception as e:
        print(f"⚠️  AD fetch failed: {e}")
        return ["jhTQ:AP-HYDERABAD-1-AD-1"]

def build_instance(ad, image_id, shape_config):
    return oci.core.models.LaunchInstanceDetails(
        availability_domain = ad,
        compartment_id      = COMPARTMENT_ID,
        display_name        = DISPLAY_NAME,
        shape               = "VM.Standard.A1.Flex",
        shape_config        = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=shape_config["ocpus"],
            memory_in_gbs=shape_config["memory_in_gbs"],
        ),
        source_details = oci.core.models.InstanceSourceViaImageDetails(
            image_id=image_id, source_type="image",
        ),
        create_vnic_details = oci.core.models.CreateVnicDetails(
            subnet_id        = SUBNET_ID,
            assign_public_ip = True,
            hostname_label   = "corecompass-prod",
        ),
        metadata={"ssh_authorized_keys": SSH_PUBLIC_KEY},
    )

def print_success(inst):
    print("\n" + "="*60)
    print("🎉🎉🎉  INSTANCE CREATED!  🎉🎉🎉")
    print("="*60)
    print(f"Name   : {inst.display_name}")
    print(f"OCID   : {inst.id}")
    print(f"AD     : {inst.availability_domain}")
    print(f"Status : {inst.lifecycle_state}")
    print("="*60)
    print("→ Go to Oracle Console → Compute → Instances")
    print("→ Wait for RUNNING status (~2 min)")
    print("→ Copy Public IP → SSH in → Deploy!")
    print("="*60)

def main():
    print("\n" + "="*60)
    print("  CoreCompass — Oracle A1.Flex GitHub Actions Retry")
    print(f"  Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("="*60 + "\n")

    try:
        compute  = oci.core.ComputeClient(config)
        identity = oci.identity.IdentityClient(config)
    except Exception as e:
        print(f"❌ OCI init failed: {e}")
        sys.exit(1)

    # Test connection
    print("Testing connection...", end=" ", flush=True)
    try:
        compute.list_shapes(COMPARTMENT_ID)
        print("✅\n")
    except oci.exceptions.ServiceError as e:
        print(f"❌\nError: {str(e)[:300]}")
        sys.exit(1)

    # Real check — do we already have one? Never trust error text for this.
    print("Checking for an existing instance...", end=" ", flush=True)
    existing = find_existing_instance(compute)
    if existing:
        print("found!\n")
        print_success(existing)
        sys.exit(0)
    print("none found.\n")

    # Auto-detect image + ADs
    image_id = get_latest_ubuntu_arm_image(compute)
    if not image_id:
        sys.exit(1)

    ads = get_availability_domains(identity)

    # Up to 20 attempts, 25s apart — fits within a 9-min job timeout
    MAX_ATTEMPTS = 20
    SLEEP_SECONDS = 25

    print(f"\nTrying up to {MAX_ATTEMPTS} attempt(s) across {len(ads)} AD(s), "
          f"{len(SHAPE_CONFIGS)} shape size(s) each...\n")

    attempt = 0
    for cycle in range(MAX_ATTEMPTS):
        for ad in ads:
            for shape_config in SHAPE_CONFIGS:
                attempt += 1
                if attempt > MAX_ATTEMPTS:
                    break

                ts = datetime.utcnow().strftime('%H:%M:%S')
                label = f"{shape_config['ocpus']}ocpu/{shape_config['memory_in_gbs']}gb"
                print(f"[{ts}] Try {attempt}/{MAX_ATTEMPTS} → {ad} ({label})", end="  ", flush=True)

                try:
                    resp = compute.launch_instance(build_instance(ad, image_id, shape_config))
                    inst = resp.data
                    print("✅ SUCCESS!\n")
                    print_success(inst)
                    sys.exit(0)

                except oci.exceptions.ServiceError as e:
                    msg = str(e)
                    if any(x in msg for x in ["Out of host capacity", "capacity", "InternalError"]):
                        print("❌ No capacity")
                    elif "LimitExceeded" in msg:
                        # Don't trust this label — verify against reality before giving up.
                        print("⚠️  LimitExceeded reported — verifying...", end=" ", flush=True)
                        real = find_existing_instance(compute)
                        if real:
                            print("confirmed, instance exists.\n")
                            print_success(real)
                            sys.exit(0)
                        else:
                            print("no instance found — treating as zero capacity, will keep retrying.")
                    elif "Conflict" in msg or "already exists" in msg.lower():
                        print("\n⚠️  Instance already exists! Check Oracle Console.")
                        sys.exit(0)
                    elif "NotAuthorized" in msg:
                        print(f"\n⛔ Auth error — check GitHub Secrets")
                        sys.exit(1)
                    elif "InvalidParameter" in msg:
                        print(f"\n⛔ Bad param — check SUBNET_ID secret")
                        print(msg[:200])
                        sys.exit(1)
                    else:
                        print(f"⚠️  {msg[:100]}")

                time.sleep(SLEEP_SECONDS)
            if attempt > MAX_ATTEMPTS:
                break
        if attempt > MAX_ATTEMPTS:
            break

    print("\n⏳ All ADs/shapes at capacity this run.")
    print("GitHub Actions will retry in 10 minutes automatically.")
    sys.exit(0)

if __name__ == "__main__":
    main()
