import time
import streamlit as st
import pandas as pd
from meraki import DashboardAPI
from meraki.exceptions import APIKeyError, APIError

# Set the page to use the full width
st.set_page_config(page_title="Meraki Dashboard", page_icon="🌐", layout="wide")


# Define a refresh interval in seconds (5 minutes)
REFRESH_INTERVAL = 2 * 60  # 5 minutes in seconds
st.sidebar.title("Meraki Networks and Device Status")

page = st.sidebar.radio("Choose page to monitor : ", ["Network Overview", "Device Status"])

# Apply CSS for the page and sidebar background color
st.markdown(
    """
    <style>
    /* Main page background color */
    .appview-container {
        background-color: #F3E4CC; /* Light brown */
    }
    
    /* Sidebar background color */
    [data-testid="stSidebar"] {
        background-color: #9B8460; /* Slightly lighter brown */
    }

    /* Sidebar and main content text color */
    .main, .sidebar-content {
        color: black; /* Darker text color for readability */
    }

    /* Column titles color */
    .dataframe thead th {
        background-color: #C7AE89; /* Light brown */
        color: black; /* Title text color */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Function to apply colors to the status cells based on value
def color_status(val):
    color = (
        'background-color: green; color: white;'
        if val in ["active", "active, ready", "online"]
        else 'background-color: red; color: black;'
    )
    return color

# Function to apply a light grey background to the device count columns
def light_grey_background(val):
    return 'background-color: #F3E4CC; color: black;'

# Function to display color-coded bars for status counts
def display_status_counts(status_counts):
    if page=="Network Overview":
        st.write("")
        st.write("")
        st.write("")
        st.write("### Organization Devices Statuses")
        st.write("The below stats represent all the devices that are under the Metdist Organization.")
        colors = {
            "online": "#4CAF50",
            "offline": "#FF5252",
            "alerting": "#FFC107",
            "dormant": "#9E9E9E"
        }
    else : 
        st.write("")
        st.write("### Network Devices Statuses")
        st.write("The below stats represent all the devices that are under the selected network.")
        st.write("")
        colors = {
            "online": "#4CAF50",
            "offline": "#FF5252",
            "alerting": "#FFC107",
            "dormant": "#9E9E9E"
    }

    def colored_bar(label, count, color):
        return f"""
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <div style="width: 80px; font-weight: bold; color: black;">{label}:</div>
            <div style="flex-grow: 1; height: 24px; background-color: {color}; width: {count*10}px; margin-left: 8px; border-radius: 4px;">
                <span style="padding-left: 8px; color: black;">{count}</span>
            </div>
        </div>
        """

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

        if page == "Network Overview":
            if 'previous_statuses' in st.session_state:
                del st.session_state['previous_statuses']
                
            network_data = []
            all_devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
            devices_df = pd.DataFrame(all_devices)

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

                    devices_in_network = devices_df[devices_df['networkId'] == network_id]
                    online_count = devices_in_network[devices_in_network['status'] == 'online'].shape[0]
                    offline_count = devices_in_network[devices_in_network['status'] == 'offline'].shape[0]
                    alerting_count = devices_in_network[devices_in_network['status'] == 'alerting'].shape[0]
                    dormant_count = devices_in_network[devices_in_network['status'] == 'dormant'].shape[0]

                    network_data.append({
                        "Network Name": network_name,
                        "Appliance Status": uplinks_summary,
                        "VPN Status": vpn_status,
                        "Online Devices": online_count,
                        "Offline Devices": offline_count,
                        "Alerting Devices": alerting_count,
                        "Dormant Devices": dormant_count,
                    })

            network_df = pd.DataFrame(network_data)
            # Remove the index by resetting it and then applying the style
            styled_df = network_df.style.applymap(color_status, subset=["Appliance Status", "VPN Status"])
            # styled_df = styled_df.applymap(light_grey_background)
            
            
            st.subheader("Network Overview")
            # st.dataframe(styled_df, use_container_width=True, height=458)
            st.write(styled_df.to_html(escape=False), unsafe_allow_html=True, use_container_width=True, height=458)

            all_org_devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
            org_devices = pd.DataFrame(all_org_devices)

            # code to display the bar s for the organization devices statuses
            network_devs_statuses = org_devices['status'].value_counts()
            st.write("")
            display_status_counts(network_devs_statuses)

        elif page == "Device Status":
            selected_network_name = st.sidebar.selectbox("Select Network", [network['name'] for network in networks])
            selected_network_id = next(network['id'] for network in networks if network['name'] == selected_network_name)

            all_devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
            devices = pd.DataFrame(all_devices)
            
            def coloured_status(value):
                return 'background-color: green; color: black;' if value == "online" else 'background-color: grey; color: black;' if value == "dormant" else 'background-color: orange; color: black;' if value=="alerting" else 'background-color: red; color: black;'

            for network_id, devices in devices.groupby('networkId'):
                if network_id == selected_network_id:
                    styled_devices = devices[['name', 'mac', 'productType', 'lastReportedAt', 'lanIp', 'status']].style.applymap(coloured_status, subset=['status'])
                    network_devs_statuses = devices['status'].value_counts()

                    st.write("")
                    display_status_counts(network_devs_statuses)
                    st.write("")
                    st.write("")
                    st.write("")
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
