#  & "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m streamlit run m5_geotab_demo.py

import streamlit as st
import requests
from datetime import datetime, timezone

# ------------------------------------------------------
# Basic config
# ------------------------------------------------------
ROUTEWARE_BASE_URL = "https://haulerpublic-api.prod.aws.rubicon.com"
# Vehicle 21531 in Routeware corresponds to M5 asset 2140
DEFAULT_ROUTEWARE_VEHICLE_ID = 21531

st.set_page_config(page_title="M5 → Geotab → Routeware Demo", layout="centered")
st.title("M5 → Geotab → Routeware Integration Demo")

# ------------------------------------------------------
# Helpers
# ------------------------------------------------------
def iso_now_utc():
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

# ------------------------------------------------------
# Step 1: Authenticate with M5
# ------------------------------------------------------
st.header("Step 1. Authenticate with M5")
m5_user = st.text_input("M5 Username")
m5_pass = st.text_input("M5 Password", type="password")

if st.button("Authenticate M5"):
    with st.spinner("Authenticating with M5..."):
        url = "https://fleetfocustest.assetworks.com/APItest/api/token"
        body = {
            "Username": m5_user.upper().strip(),
            "Password": m5_pass,
            "Site": "stpaul"
        }
        headers = {"Content-Type": "application/json"}

        r = requests.post(url, json=body, headers=headers)
        st.write(f"Status: {r.status_code}")
        try:
            data = r.json()
            st.subheader("Raw M5 Response")
            st.json(data)

            if (
                r.status_code == 200
                and isinstance(data, dict)
                and "items" in data
                and isinstance(data["items"], list)
                and len(data["items"]) > 0
            ):
                token = data["items"][0]
                st.session_state["m5_token"] = token
                st.session_state["m5_user"] = m5_user
                st.success("M5 authentication successful!")
                st.code(token[:50] + "...", language="text")
            else:
                st.error("Token not found in 'items' array of response.")
                st.write("Response keys:", list(data.keys()))
        except Exception as e:
            st.error(f"Error parsing response: {e}")

# ------------------------------------------------------
# Step 2: Get Asset 2140 from M5
# ------------------------------------------------------
st.header("Step 2. Get Asset 2140 from M5")

if st.button("Get Asset Info"):
    token = st.session_state.get("m5_token")

    if not token:
        st.warning("Please authenticate to M5 first.")
    else:
        url = "https://fleetfocustest.assetworks.com/APItest/api/v1/assets/2140"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        with st.spinner("Retrieving asset info from M5..."):
            r = requests.get(url, headers=headers)
            st.write(f"Status: {r.status_code}")
            try:
                data = r.json()
                st.subheader("M5 Asset Response")
                st.json(data)

                if r.status_code == 200:
                    st.success("Asset info retrieved successfully.")
                    st.session_state["m5_asset"] = data
                else:
                    st.error("Failed to retrieve asset info.")
            except Exception as e:
                st.error(f"Error reading response: {e}")

# ------------------------------------------------------
# Step 2.5: Review/Edit Comment before Sending to Geotab & Routeware
# ------------------------------------------------------
st.header("Step 2.5. Review or Edit Comment from M5")

edited_comment = ""
if "m5_asset" in st.session_state:
    asset = st.session_state["m5_asset"]

    # Safely extract comments from items[0].comments
    m5_comment = None
    try:
        if isinstance(asset, dict) and "items" in asset and len(asset["items"]) > 0:
            first_item = asset["items"][0]
            m5_comment = first_item.get("comments", "")
    except Exception as e:
        st.warning(f"Could not read comment: {e}")

    if not m5_comment:
        m5_comment = "No comment found for this asset."

    st.subheader("Original Comment from M5:")
    st.code(m5_comment, language="text")

    edited_comment = st.text_area(
        "Edit the comment (will be used for Geotab & Routeware):",
        value=m5_comment,
        height=150
    )

    st.session_state["edited_comment"] = edited_comment
    st.success("Comment ready to use in later steps.")
else:
    st.info("Retrieve asset info first to display and edit its comment.")

# ------------------------------------------------------
# Step 3: Authenticate with Geotab
# ------------------------------------------------------
st.header("Step 3. Authenticate with Geotab")

geotab_user = st.text_input("Geotab Username")
geotab_pass = st.text_input("Geotab Password", type="password")

if st.button("Authenticate Geotab"):
    with st.spinner("Authenticating with Geotab..."):
        try:
            url = "https://my.geotab.com/apiv1/"
            headers = {"Content-Type": "application/json"}
            body = {
                "method": "Authenticate",
                "params": {
                    "userName": geotab_user.strip(),
                    "password": geotab_pass.strip(),
                    "database": "city_of_saint_paul"
                },
                "id": 1,
                "jsonrpc": "2.0"
            }

            r = requests.post(url, json=body, headers=headers)
            st.write(f"Status: {r.status_code}")
            data = r.json()
            st.json(data)

            if r.status_code == 200 and "result" in data:
                creds = data["result"]["credentials"]
                session_id = creds["sessionId"]
                user_name = creds["userName"]

                st.session_state["geotab_session"] = {
                    "session_id": session_id,
                    "user": user_name
                }

                st.success("Geotab authentication successful!")
                st.code(session_id, language="text")
            else:
                st.error("Failed to authenticate Geotab. Check credentials or database name.")

        except Exception as e:
            st.error(f"Error: {e}")

# ------------------------------------------------------
# Step 4: Prepare & Update Geotab Device Comment
# ------------------------------------------------------
st.header("Step 4. Update Geotab Device Comment")

geo = st.session_state.get("geotab_session")
edited_comment = st.session_state.get("edited_comment", "")
m5_user_state = st.session_state.get("m5_user", m5_user)

if st.button("Prepare Geotab Comment Update"):
    if not geo:
        st.warning("Authenticate with Geotab first.")
    elif not edited_comment:
        st.warning("No M5 comment text found to send.")
    else:
        geotab_url = "https://my.geotab.com/apiv1/"
        creds = {
            "database": "city_of_saint_paul",
            "sessionId": geo["session_id"],
            "userName": geo["user"]
        }

        # 1️⃣ Find the device whose name starts with 2140
        find_payload = {
            "method": "Get",
            "params": {
                "typeName": "Device",
                "search": {"name": "2140%"},
                "credentials": creds
            },
            "id": 1,
            "jsonrpc": "2.0"
        }
        r_get = requests.post(geotab_url, json=find_payload)
        devices = r_get.json().get("result", [])

        if not devices:
            st.error("No Geotab device found with name beginning with 2140.")
        else:
            device = devices[0]
            st.session_state["geotab_device"] = device
            st.session_state["existing_comment"] = device.get("comment", "")
            st.session_state["prepared_comment"] = edited_comment
            st.session_state["show_comment_editor"] = True

# ✅ Show the comment edit UI if device info has been prepared
if st.session_state.get("show_comment_editor"):
    device = st.session_state["geotab_device"]
    existing_comment = st.session_state.get("existing_comment", "")
    edited_comment = st.session_state.get("prepared_comment", "")
    device_name = device["name"]

    st.subheader(f"Current Geotab Comment for {device_name}:")
    st.code(existing_comment if existing_comment else "[No existing comment]", language="text")

    append_option = st.checkbox("Append M5 comment to existing Geotab comment", value=True)

    now = datetime.now().strftime("%m/%d/%y")
    new_entry = f"[{now}: M5 - {m5_user_state}] {edited_comment.strip()}"
    if append_option:
        separator = "\n" if existing_comment.endswith("\n") else "\n\n"
        combined_comment = (existing_comment + separator + new_entry).strip()
    else:
        combined_comment = new_entry

    final_comment = st.text_area(
        "Final Comment to send to Geotab:",
        value=combined_comment,
        height=200
    )

    # Store for Routeware, too
    st.session_state["final_comment_for_routeware"] = final_comment
    st.session_state["new_entry_for_routeware"] = new_entry

    if st.button("Update Comment in Geotab"):
        geotab_url = "https://my.geotab.com/apiv1/"
        geo = st.session_state.get("geotab_session")
        creds = {
            "database": "city_of_saint_paul",
            "sessionId": geo["session_id"],
            "userName": geo["user"]
        }

        update_payload = {
            "method": "Set",
            "params": {
                "typeName": "Device",
                "entity": {"id": device["id"], "comment": final_comment},
                "credentials": creds
            },
            "id": 2,
            "jsonrpc": "2.0"
        }
        r_set = requests.post(geotab_url, json=update_payload)

        if r_set.status_code == 200 and "error" not in r_set.json():
            st.success(f"Comment successfully updated for {device_name}")
            st.session_state["show_comment_editor"] = False

            # Optional read-back verification
            verify_payload = {
                "method": "Get",
                "params": {
                    "typeName": "Device",
                    "search": {"id": device["id"]},
                    "credentials": creds
                },
                "id": 3,
                "jsonrpc": "2.0"
            }
            r_verify = requests.post(geotab_url, json=verify_payload)
            if r_verify.status_code == 200:
                new_data = r_verify.json().get("result", [])
                if new_data:
                    st.subheader("🔄 Verified Updated Comment:")
                    st.code(new_data[0].get("comment", ""), language="text")
        else:
            st.error("Failed to update device comment.")
            st.text(r_set.text)

    if st.button("Cancel / Go Back"):
        st.session_state["show_comment_editor"] = False
        st.experimental_rerun()

# ------------------------------------------------------
# Step 5: Routeware – Create Job
# ------------------------------------------------------
st.header("Step 5. Create Routeware Job for Vehicle 21531")

st.markdown("This step uses your Routeware API key and the JobCreate schema.")

routeware_api_key = st.text_input("Routeware API Key", type="password")

# These are now KNOWN values from your tenant:
vehicle_type_id = 9
pickup_type_id = 1

# Allow user to choose from valid priority + reason codes:
priority_options = {1: "High", 2: "Medium", 3: "Low"}
reason_options = {
    16: "Miscellaneous",
    3: "Clean-up",
    17: "Improper Set Out",
}

priority_choice = st.selectbox("Job Priority", options=list(priority_options.keys()),
                               format_func=lambda x: priority_options[x])

reason_choice = st.selectbox("Reason Code", options=list(reason_options.keys()),
                             format_func=lambda x: reason_options[x])

job_comment = st.text_area("Route Note / Comment", 
                           value=st.session_state.get("edited_comment", ""))

scheduled_date_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

# Create work order number automatically
work_order_number = f"M5-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

if st.button("Create Routeware Job_"):
    if not routeware_api_key:
        st.warning("Enter Routeware API key first.")
    else:
        job_body = {
            "workOrderNumber": work_order_number,
            "jobDate": scheduled_date_iso,
            "serviceContractId": 0,
            "vehicleTypeId": vehicle_type_id,
            "pickupTypeId": pickup_type_id,
            "routeNote": job_comment,
            "routeTemplateId": 0,
            "reasonCodeTypeId": reason_choice,
            "jobPriorityTypeId": priority_choice
        }

        st.write("Payload being sent to Routeware:")
        st.json(job_body)

        headers = {
            "Content-Type": "application/json",
            "x-api-key": routeware_api_key.strip()
        }

        url = "https://haulerpublic-api.prod.aws.rubicon.com/api/job"
        with st.spinner("Creating Routeware job..."):
            r = requests.post(url, json=job_body, headers=headers)

        st.write("Status Code:", r.status_code)
        st.write("Response:", r.text)
        try:
            st.json(r.json())
        except:
            pass

        if r.status_code in (200, 201):
            st.success(f"Routeware job created successfully! Work Order: {work_order_number}")

