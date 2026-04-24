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
        return ["SBqE:AP-HYDERABAD-1-AD-1"]

def build_instance(ad, image_id):
    return oci.core.models.LaunchInstanceDetails(
        availability_domain = ad,
        compartment_id      = COMPARTMENT_ID,
        display_name        = "corecompass-prod",
        shape               = "VM.Standard.A1.Flex",
        shape_config        = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=4, memory_in_gbs=24,
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

    # Auto-detect image + ADs
    image_id = get_latest_ubuntu_arm_image(compute)
    if not image_id:
        sys.exit(1)

    ads = get_availability_domains(identity)

    print(f"\nTrying {len(ads)} AD(s) this run...\n")

    for attempt, ad in enumerate(ads * 2, 1):
        ts = datetime.utcnow().strftime('%H:%M:%S')
        print(f"[{ts}] Try {attempt} → {ad}", end="  ", flush=True)

        try:
            resp = compute.launch_instance(build_instance(ad, image_id))
            inst = resp.data
            print("✅ SUCCESS!\n")
            print("="*60)
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
            sys.exit(0)

        except oci.exceptions.ServiceError as e:
            msg = str(e)
            if any(x in msg for x in ["Out of host capacity", "capacity", "InternalError"]):
                print("❌ No capacity")
            elif "LimitExceeded" in msg:
                print("\n⚠️  Free tier limit reached — may already have instance!")
                sys.exit(0)
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

        time.sleep(10)

    print("\n⏳ All ADs at capacity this run.")
    print("GitHub Actions will retry in 10 minutes automatically.")
    sys.exit(0)

if __name__ == "__main__":
    main()
