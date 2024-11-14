import time
import streamlit as st
import pandas as pd
from meraki import DashboardAPI
from meraki.exceptions import APIKeyError, APIError

# Set the page to use the full width and a dark theme
st.set_page_config(page_title="Meraki Dashboard", page_icon="🌐", layout="wide")

# Define a refresh interval in seconds (5 minutes)
REFRESH_INTERVAL = 2 * 60  # 5 minutes in seconds

# Custom CSS for styling
st.markdown(
    """
    <style>
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
    .css-1aumxhk {
        background-color: #1f1f2e;
        color: #cddc39;
    }
    .css-10trblm {
        color: #ffffff;
    }
    .css-15zrgzn {
        color: #cddc39;
    }
    .css-1d391kg {
        background-color: #1f1f2e;
    }
    .centered-container {
        display: flex;
        justify-content: center;
        padding-top: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Function to apply colors to the status cells based on value
def color_status(val):
    color = (
        'background-color: green; color: white;'
        if val == "active" or val == "active, ready" or val == "online"
        else 'background-color: red; color: white;'
    )
    return color

# Function to display color-coded bars for status counts
def display_status_counts(status_counts):
    # st.write("### Devices Status in Network")
    colors = {
        "online": "#4CAF50",
        "offline": "#FF5252",
        "alerting": "#FFC107",
        "dormant": "#9E9E9E"
    }

    def colored_bar(label, count, color):
        return f"""
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <div style="width: 80px; font-weight: bold; color: #FFFFFF;">{label}:</div>
            <div style="flex-grow: 1; height: 24px; background-color: {color}; width: {count*10}px; margin-left: 8px; border-radius: 4px;">
                <span style="padding-left: 8px; color: white;">{count}</span>
            </div>
        </div>
        """

    colour_bars(status_counts, colors, colored_bar)

def colour_bars(status_counts, colors, colored_bar):
    st.markdown(
        colored_bar("Online", status_counts.get('online', 0), colors['online']),
        unsafe_allow_html=True
    )
    st.markdown(
        colored_bar("Offline", status_counts.get('offline', 0), colors['offline']),
        unsafe_allow_html=True
    )
    st.markdown(
        colored_bar("Alerting", status_counts.get('alerting', 0), colors['alerting']),
        unsafe_allow_html=True
    )
    st.markdown(
        colored_bar("Dormant", status_counts.get('dormant', 0), colors['dormant']),
        unsafe_allow_html=True
    )

def main():
    if 'countdown' not in st.session_state:
        st.session_state['countdown'] = REFRESH_INTERVAL
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'previous_statuses' not in st.session_state:
        st.session_state['previous_statuses'] = {}

    st.sidebar.title("Meraki Networks and Device Status")
    
    # Page navigation in the sidebar
    page = st.sidebar.radio("Navigate", ["Networks Overview", "Device Status"])

    if not st.session_state['logged_in']:
        api_key = st.sidebar.text_input("Enter your Meraki API Key", type="password")
        if api_key:
            try:
                dashboard = DashboardAPI(api_key)
                organizations = dashboard.organizations.getOrganizations()
                if organizations:
                    st.sidebar.success("Successfully connected to Meraki API")
                    st.session_state['api_key'] = api_key
                    st.session_state['logged_in'] = True
                    st.session_state['dashboard'] = dashboard
                else:
                    st.sidebar.error("No organizations found for this API key.")
            except (APIKeyError, APIError) as e:
                st.sidebar.error(f"API Error: {e}")
    else:
        dashboard = st.session_state['dashboard']

    if st.session_state['logged_in']:
        dashboard = st.session_state['dashboard']
        organizations = dashboard.organizations.getOrganizations()
        org_id = organizations[0]["id"]
        networks = dashboard.organizations.getOrganizationNetworks(org_id)
        excluded_network_names = ["UK transfer", "Metdist ISL-S", "Metdist ISL-Borealis", "Metdist ISL-A"]

        if page == "Networks Overview":
            network_data = []
            for network in networks:
                if network['name'] not in excluded_network_names:
                    network_id = network['id']
                    network_name = network['name']
                    
                    appliance_status = dashboard.appliance.getOrganizationApplianceUplinkStatuses(org_id)
                    appliance_for_network = next((appl for appl in appliance_status if appl['networkId'] == network_id), None)
                    uplinks = appliance_for_network['uplinks'] if appliance_for_network else "N/A"
                    uplinks_summary = ", ".join([uplink['status'] for uplink in uplinks]) if isinstance(uplinks, list) else uplinks

                    vpn_statuses = dashboard.appliance.getOrganizationApplianceVpnStatuses(org_id)
                    vpn_for_network = next((vpn for vpn in vpn_statuses if vpn['networkId'] == network_id), None)
                    vpn_status = vpn_for_network['deviceStatus'] if vpn_for_network else "N/A"

                    prev_status = st.session_state['previous_statuses'].get(network_name, {})
                    prev_appliance_status = prev_status.get("Appliance Status", None)
                    prev_vpn_status = prev_status.get("VPN Status", None)

                    if prev_appliance_status and prev_appliance_status != uplinks_summary:
                        st.warning(f"Appliance status for '{network_name}' changed from '{prev_appliance_status}' to '{uplinks_summary}'")
                    if prev_vpn_status and prev_vpn_status != vpn_status:
                        st.warning(f"VPN status for '{network_name}' changed from '{prev_vpn_status}' to '{vpn_status}'")

                    st.session_state['previous_statuses'][network_name] = {
                        "Appliance Status": uplinks_summary,
                        "VPN Status": vpn_status,
                    }

                    network_data.append({
                        "Network Name": network_name,
                        "Appliance Status": uplinks_summary,
                        "VPN Status": vpn_status,
                    })

            network_df = pd.DataFrame(network_data)
            styled_df = network_df.style.applymap(color_status, subset=["Appliance Status", "VPN Status"])
            st.subheader("Networks Overview")
            st.write("")
            st.dataframe(styled_df, use_container_width=True, height=458)

        elif page == "Device Status":
            selected_network_name = st.sidebar.selectbox("Select Network", [network['name'] for network in networks])
            selected_network_id = next(network['id'] for network in networks if network['name'] == selected_network_name)

            all_devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
            devices = pd.DataFrame(all_devices)
            
            def coloured_status(value):
                return 'background-color: green; color: white;' if value == "online" else 'background-color: grey; color: white;' if value == "dormant" else 'background-color: orange; color: white;' if value=="alerting" else 'background-color: red; color: white;'

            for network_id, devices in devices.groupby('networkId'):
                if network_id == selected_network_id:
                    styled_devices = devices[['name', 'mac', 'productType', 'lastReportedAt', 'lanIp', 'status']].style.applymap(coloured_status, subset=['status'])
                    network_devs_statuses = devices['status'].value_counts()                    
                    st.write("")
                    st.write("")
                    st.write("")
                    st.write(f"### Devices Status in {selected_network_name} Network")
                    st.write("")
                    st.write("")
                    st.write("")
                    display_status_counts(network_devs_statuses)
                    st.write("")
                    st.write("")
                    st.subheader(f"Devices in {selected_network_name} Network")
                    st.markdown('<div class="centered-container">', unsafe_allow_html=True)
                    st.write(styled_devices.to_html(escape=False), unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

        countdown_placeholder = st.sidebar.empty()
        for seconds_left in range(st.session_state['countdown'], 0, -1):
            minutes, seconds = divmod(seconds_left, 60)
            countdown_placeholder.info(f"Next refresh in: {minutes:02d}:{seconds:02d}")
            time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
