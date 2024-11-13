import time
import streamlit as st
import pandas as pd
from meraki import DashboardAPI
from meraki.exceptions import APIKeyError, APIError

# Set the page to use the full width and a dark theme
st.set_page_config(page_title="Meraki Dashboard", page_icon="🌐", layout="wide")

# Define a refresh interval in seconds (5 minutes)
REFRESH_INTERVAL = 2 * 60  # 5 minutes in seconds

# Custom CSS to style the dashboard with a black background and green/yellow accents
st.markdown(
    """
    <style>
    /* Apply a black background color and white text for the main container */
    .reportview-container {
        background-color: #000000;
    }
    .main .block-container {
        background-color: #000000;
        color: #ffffff;
        padding-top: 2rem;
        padding-right: 2rem;  
        padding-left: 2rem;
    }
    /* Sidebar styling */
    .css-1aumxhk {
        background-color: #1f1f2e;
        color: #cddc39;  /* Light green text color for the sidebar */
    }
    /* General text color */
    .css-10trblm {  /* Main text color */
        color: #ffffff;
    }
    .css-15zrgzn {  /* Title and header color */
        color: #cddc39;
    }
    /* Dataframe styling for color-coding status */
    .css-1d391kg {
        background-color: #1f1f2e;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Function to apply colors to the status cells based on value
def color_status(val):
    color = (
        'background-color: green; color: white;'
        if val=="active" or val == "active, ready" or val == "online"
        else 'background-color: red; color: white;'
    )
    return color

def main():
    # Initialize countdown and login flag in session_state if not already set
    if 'countdown' not in st.session_state:
        st.session_state['countdown'] = REFRESH_INTERVAL
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False  # Tracks if user has successfully logged in
    if 'previous_statuses' not in st.session_state:
        st.session_state['previous_statuses'] = {}  # Tracks previous appliance and VPN statuses for alerts
    
    # Title and description
    st.sidebar.title("Meraki Networks and Device Status")

    # Prompt for API Key in the sidebar
    if not st.session_state['logged_in']:
        api_key = st.sidebar.text_input("Enter your Meraki API Key", type="password")
        if api_key:
            try:
                # Try initializing the Meraki API client
                dashboard = DashboardAPI(api_key)
                
                # Test if we can fetch organizations
                organizations = dashboard.organizations.getOrganizations()
                if organizations:
                    st.sidebar.success("Successfully connected to Meraki API")
                    st.session_state['api_key'] = api_key
                    st.session_state['logged_in'] = True  # Set login flag
                    st.session_state['dashboard'] = dashboard  # Store dashboard client
                else:
                    st.sidebar.error("No organizations found for this API key.")
            except (APIKeyError, APIError) as e:
                st.sidebar.error(f"API Error: {e}")
    else:
        dashboard = st.session_state['dashboard']
    
    # Sidebar navigation for pages if logged in
    if st.session_state['logged_in']:
        page = st.sidebar.radio("Select Page", ["Network Overview", "Devices in Network"])

        # Retrieve organization information
        organizations = dashboard.organizations.getOrganizations()
        org_id = organizations[0]["id"]
        networks = dashboard.organizations.getOrganizationNetworks(org_id)
        excluded_network_names = ["UK transfer", "Metdist ISL-S", "Metdist ISL-Borealis", "Metdist ISL-A"]

        # Network Overview Page
        if page == "Network Overview":
            # Fetch network and device data
            network_data = []
            for network in networks:
                if network['name'] not in excluded_network_names:
                    network_id = network['id']
                    network_name = network['name']
                    
                    # Fetch appliance status
                    appliance_status = dashboard.appliance.getOrganizationApplianceUplinkStatuses(org_id)
                    appliance_for_network = next((appl for appl in appliance_status if appl['networkId'] == network_id), None)
                    uplinks = appliance_for_network['uplinks'] if appliance_for_network else "N/A"
                    uplinks_summary = ", ".join([uplink['status'] for uplink in uplinks]) if isinstance(uplinks, list) else uplinks

                    # Fetch VPN status
                    vpn_statuses = dashboard.appliance.getOrganizationApplianceVpnStatuses(org_id)
                    vpn_for_network = next((vpn for vpn in vpn_statuses if vpn['networkId'] == network_id), None)
                    vpn_status = vpn_for_network['deviceStatus'] if vpn_for_network else "N/A"

                    # Alert for status changes
                    prev_status = st.session_state['previous_statuses'].get(network_name, {})
                    prev_appliance_status = prev_status.get("Appliance Status", None)
                    prev_vpn_status = prev_status.get("VPN Status", None)

                    # Check and display alerts if there is a change in status
                    if prev_appliance_status and prev_appliance_status != uplinks_summary:
                        st.warning(f"Appliance status for '{network_name}' changed from '{prev_appliance_status}' to '{uplinks_summary}'")
                    if prev_vpn_status and prev_vpn_status != vpn_status:
                        st.warning(f"VPN status for '{network_name}' changed from '{prev_vpn_status}' to '{vpn_status}'")

                    # Update the session state with the current statuses
                    st.session_state['previous_statuses'][network_name] = {
                        "Appliance Status": uplinks_summary,
                        "VPN Status": vpn_status,
                    }

                    network_data.append({
                        "Network Name": network_name,
                        "Appliance Status": uplinks_summary,
                        "VPN Status": vpn_status,
                    })

            # Display network data in a DataFrame with color-coded statuses
            network_df = pd.DataFrame(network_data)
            styled_df = network_df.style.applymap(color_status, subset=["Appliance Status", "VPN Status"])
            st.subheader("Network Overview")
            st.dataframe(styled_df, use_container_width=True, height=458)

        # Devices in Network Page
        elif page == "Devices in Network":
            selected_network_name = st.sidebar.selectbox("Select Network", [network['name'] for network in networks])
            selected_network_id = next(network['id'] for network in networks if network['name'] == selected_network_name)

            all_devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)

            devices = dashboard.networks.getNetworkDevices(selected_network_id)
            # device_data = [{"Device Name": dev.get('name', 'N/A'), "MAC": dev.get('mac', 'N/A'), "Serial": dev.get('serial', 'N/A'), "Status": dev.get('status', 'N/A')} for dev in devices]

            devices_df = pd.DataFrame(all_devices)

            # CSS for centering the container
            st.markdown(
                """
                <style>
                .centered-container {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding-top: 2rem;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            # Retrieve the `networkId` corresponding to the selected network name
            selected_network_id = next((network['id'] for network in networks if network['name'] == selected_network_name), None)

            # Fetch all devices' statuses
            try:
                all_devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
            except Exception as e:
                st.error(f"Error fetching device statuses: {e}")
                all_devices = []

            # Ensure all_devices has data before proceeding
            if all_devices:
                # Convert the list of devices to a pandas DataFrame
                devices_df = pd.DataFrame(all_devices)


            # Function to apply colors based on device status
        def coloured_status(value):
            if value == "online":
                color = 'background-color: green; color: white;'
            elif value == "dormant":
                color = 'background-color: orange; color: white;'
            else:
                color = 'background-color: red; color: white;'
            return color


        for network_id, devices in devices_df.groupby('networkId'):
            if network_id == selected_network_id:
                st.markdown('<div class="centered-container">', unsafe_allow_html=True)  # Start centered div
                st.subheader(f"Devices in {selected_network_name} Network")

                # Apply colored status formatting
                styled_devices = devices[['name', 'mac', 'status']].style.applymap(coloured_status, subset=['status'])

                # Display the styled DataFrame in the center
                st.write(styled_devices.to_html(escape=False), unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)  # End centered div


    # Countdown timer for the next refresh if logged in
    if st.session_state['logged_in']:
        countdown_placeholder = st.sidebar.empty()
        for seconds_left in range(st.session_state['countdown'], 0, -1):
            minutes, seconds = divmod(seconds_left, 60)
            countdown_placeholder.info(f"Next refresh in: {minutes:02d}:{seconds:02d}")
            time.sleep(1)

        # Trigger automatic refresh after countdown
        st.rerun()

if __name__ == "__main__":
    main()
