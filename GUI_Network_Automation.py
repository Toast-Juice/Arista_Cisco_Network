import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import json
from netmiko import ConnectHandler
import os
import datetime
import sys

# Create the root window first
root = tk.Tk()
root.withdraw()  # Hide it while selecting file

LAST_USED_FILE = "last_used.json"

# Load last-used path if it exists
last_path = ""
if os.path.exists(LAST_USED_FILE):
    with open(LAST_USED_FILE) as f:
        try:
            last_path = json.load(f).get("last_path", "")
        except json.JSONDecodeError:
            pass

# Ask to reuse last file if valid
if last_path and os.path.exists(last_path):
    use_last = messagebox.askyesno("Use Previous File", f"Use last device file?\n{last_path}")
    if not use_last:
        last_path = ""

# Ask user to select file if needed
if not last_path:
    last_path = filedialog.askopenfilename(
        title="Select Device JSON File",
        filetypes=[("JSON files", "*.json")]
    )
    if not last_path:
        messagebox.showerror("File Required", "You must select a device JSON file to continue.")
        root.destroy()
        sys.exit()

# Save path for future use
with open(LAST_USED_FILE, "w") as f:
    json.dump({"last_path": last_path}, f)

# Load Devices
with open(last_path) as f:
    devices = json.load(f)

# Now show the GUI
root.deiconify()

# GUI Layout
root.title("Network Configuration GUI")

device_names = list(devices.keys())
states = sorted({dev["state"] for dev in devices.values()})
sites = sorted({dev["site"] for dev in devices.values()})

# SSH Helper to get into the device
def ssh_connect(device_name, username, password):
    dev = devices[device_name]
    # Only keep keys that Netmiko needs
    device_params = {
        "device_type": dev["device_type"],
        "ip": dev["ip"],
        "username": username,
        "password": password
    }
    try:
        return ConnectHandler(**device_params)
    except Exception as e:
        messagebox.showerror("Connection Error", f"{device_name}: {e}")
        return None

# Tasks

# Save the running config to a file
def get_running_config(conn, name):
    # Generate default filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_filename = f"{name}_running_config_{timestamp}.txt"

    # Ask user where to save the file
    save_path = filedialog.asksaveasfilename(
        title="Save Running Config As",
        initialfile=default_filename,
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt")]
    )

    if not save_path:
        return f"Save cancelled for {name}"

    # Get and save config
    save_config(conn, name)
    output = conn.send_command("show running-config")
    with open(save_path, "w") as f:
        f.write(output)
    return f"Saved config for {name} on device and to {save_path}"

# List all available interfaces on a specific switch
def interface_list(conn, interface):
    try:
        status = conn.send_command("show interface status")
        return f"Interface status list:\n {status}"
    except Exception as e:
        return f"Error retrieving interface list: {e}"
    
# List interface info for specific interface
def show_interface_info(conn, interface):
    try:
        # Get interface status
        status = conn.send_command(f"show interface {interface} status")
        # Get running config for the interface
        running_cfg = conn.send_command(f"show running-config interface {interface}")
        return f"Interface Status:\n{status}\n\nRunning Config:\n{running_cfg}"
    except Exception as e:
        return f"Error retrieving interface info: {e}"

# Configure a trunk port on designated switch(es)
def configure_trunk(conn, name):
    intf_list = interface_list(conn, name)
    intf = simpledialog.askstring("Trunk Port", f"{intf_list}\nEnter interface for {name}:", parent=root)
    desc = simpledialog.askstring("Trunk Port", f"Enter Description for {name} interface {intf}:", parent=root)
    if not intf:
        return "Skipped"
    if not desc:
        return ""
    
    info = show_interface_info(conn, intf)
    proceed = messagebox.askyesno(f"{intf} Info", f"{info}\n\nProceed with trunk configuration?")
    if not proceed:
        return "Skipped"

    output = conn.send_config_set([
        f"default interface {intf}",
        f"interface {intf}",
        "switchport mode trunk",
        "switchport trunk allow vlan 30-39,50",
        "switchport trunk native vlan 99",
        f"description **{desc}**",
        "no shutdown"
    ])
    conn.send_command("copy run start")
    running = conn.send_command(f"sho run int {intf}")
    return f"Configured {intf} as trunk and saved\n{running}"

# Configure Access port on designated switch(es)
def configure_access(conn, name):
    intf_list = interface_list(conn, name)
    intf = simpledialog.askstring("Access Port", f"{intf_list}\nEnter interface for {name}:", parent=root)
    if not intf:
        return "Skipped"
    info = show_interface_info(conn, intf)
    phone = messagebox.askyesno("Phone Included?", f"Does interface {intf} include data and voice?")   # Ask if there is a phone or not
    if phone:
        phone_data(conn, name, intf)
        # Sends results from phone_data
        result = conn.send_command(f"show run int {intf}")
        return f"Configured int {intf} for voice and data\n{result}"
    proceed = messagebox.askyesno(f"{intf} Info", f"{info}\n\nProceed with access port configuration?")
    if not proceed:
        return "Skipped"
    vlan = simpledialog.askstring("Access Port", f"Enter VLAN for {name} interface {intf}:", parent=root)
    desc = simpledialog.askstring("Access Port", f"Enter Description for {name} interface {intf}:", parent=root)
    if not vlan:
        return "Skipped"
    if not desc:
        return ""
    
    output = conn.send_config_set([
        f"default interface {intf}",
        f"interface {intf}",
        "switchport mode access",
        f"switchport access vlan {vlan}",
        f"description **{desc}**",
        "spanning-tree portfast",
        "no shutdown"
    ])
    conn.send_command("copy run start")
    running = conn.send_command(f"sho run int {intf}")
    return f"Configured {intf} for VLAN {vlan} and saved\n{running}"

# Save the configurations on the switch
def save_config(conn, name):
    conn.send_command("copy run start")
    return "Saved configuration"

# Show the vlans on each interface
def vlan_intf(conn, name):
    output = conn.send_command("show vlan")
    return output

# Show running config on a specific interface
def intf_running(conn, name):
    intf_list = interface_list(conn, name)
    intf = simpledialog.askstring("Default And Shutdown Interface", f"{intf_list}\nEnter interface for {name}:", parent=root)
    if not intf:
        return "No interface provided."
    output = conn.send_command(f"show run int {intf}")
    return output

# Shutdown and Default Interface
def shut_intf(conn, name):
    intf_list = interface_list(conn, name)
    intf = simpledialog.askstring("Trunk Port", f"{intf_list}\nEnter interface for {name}:", parent=root)
    if not intf:
        return "No interface provided."
    info = show_interface_info(conn, intf)
    proceed = messagebox.askyesno(f"{intf} Info", f"{info}\n\nProceed with default and shutdown interface configuration?")
    if not proceed:
        return "Skipped"
    output = conn.send_config_set([
        f"default interface {intf}",
        f"interface {intf}",
        "switchport mode access",
        f"switchport access vlan 666",
        f"description **SHUTDOWN**",
        "shutdown"
    ])
    conn.send_command("copy run start")
    running = conn.send_command(f"sho run int {intf}")
    return f"Defaulted and Shutdown int {intf} and saved\n{running}"

# Set an interface to include a phone and data
def phone_data(conn, name, intf):
    dev_type = devices[name]["device_type"]
    if dev_type in ("cisco_ios", "cisco_iosxe"):   
        output = conn.send_config_set([
        f"default interface {intf}",
        f"interface {intf}",
        "switchport mode access",
        "switchport access vlan 1",
        "switchport voice vlan 2",
        "description **USER + PHONE CISCO**",
        "spanning-tree portfast"
        "no shutdown"
        ])
    else:
        output = conn.send_config_set([
        f"default interface {intf}",
        f"interface {intf}",
        "switchport mode trunk",
        "switchport trunk native vlan 1",   # The native vlan is the vlan used by the computer
        "switchport trunk allow vlan 1,2",
        "description **USER + PHONE ARISTA**",
        "spanning-tree portfast",
        "no shutdown"
        ])
    conn.send_command("copy run start")
    # Returns back to configure_access
    return


# Device selection logic
def get_selected_devices():
    scope = scope_var.get()
    if scope == "All":
        return device_names
    elif scope == "Single":
        return [device_combo.get()] if device_combo.get() in device_names else []
    elif scope == "Multiple":
        return [device_listbox.get(i) for i in device_listbox.curselection()]
    elif scope == "State":
        return [name for name, dev in devices.items() if dev["state"] == state_combo.get()]
    elif scope == "Site":
        return [name for name, dev in devices.items() if dev["site"] == site_combo.get()]
    return []

# Run selected task
def perform_task():
    username = user_entry.get()
    password = pass_entry.get()
    if not username or not password:
        messagebox.showerror("Missing Info", "Please enter credentials.")
        return

    task = action_var.get()
    targets = get_selected_devices()
    if not targets:
        messagebox.showwarning("No Devices", "No devices selected.")
        return

    results = []
    for name in targets:
        conn = ssh_connect(name, username, password)
        if conn:
            if task == "Get Running Config":
                result = get_running_config(conn, name)
            elif task == "Configure Trunk Port":
                result = configure_trunk(conn, name)
            elif task == "Configure Access Port":
                result = configure_access(conn, name)
            elif task == "Save Configuration":
                result = save_config(conn, name)
            elif task == "Interface Running Config":
                result = intf_running(conn, name)
            elif task == "Show VLAN Interfaces":
                result = vlan_intf(conn, name)
            elif task == "Shutdown Interface":
                result = shut_intf(conn, name)
            save_config(conn, name)
            conn.disconnect()
            results.append(f"{name}: {result}")
    messagebox.showinfo("Task Complete", "\n".join(results))

# Show/hide widgets
def update_scope_inputs(*args):
    for widget in [device_combo, state_combo, site_combo, device_listbox]:
        widget.grid_remove()

    if scope_var.get() == "Single":
        device_combo.grid(row=5, column=1)
    elif scope_var.get() == "Multiple":
        device_listbox.grid(row=5, column=1)
    elif scope_var.get() == "State":
        state_combo.grid(row=5, column=1)
    elif scope_var.get() == "Site":
        site_combo.grid(row=5, column=1)



# Username Credentials
tk.Label(root, text="Username:").grid(row=0, column=0, sticky="e")
user_entry = tk.Entry(root)
user_entry.grid(row=0, column=1)

# Password Credentials
tk.Label(root, text="Password:").grid(row=1, column=0, sticky="e")
pass_entry = tk.Entry(root, show="*")
pass_entry.grid(row=1, column=1)

# Select a Task
tk.Label(root, text="Action:").grid(row=2, column=0, sticky="e")
action_var = tk.StringVar(value="Get Running Config")
ttk.Combobox(root, textvariable=action_var, values=[
    "Get Running Config", "Configure Trunk Port", "Configure Access Port","Interface Running Config", "Show VLAN Interfaces", "Shutdown Interface", "Save Configuration", 
]).grid(row=2, column=1)

# Select The Scope
tk.Label(root, text="Scope:").grid(row=3, column=0, sticky="e")
scope_var = tk.StringVar(value="All")
scope_box = ttk.Combobox(root, textvariable=scope_var, values=[
    "All", "Single", "Multiple", "State", "Site"
])
scope_box.grid(row=3, column=1)
scope_var.trace("w", update_scope_inputs)

# Conditional selectors (row 5)
tk.Label(root, text="Selector:").grid(row=4, column=0, sticky="e")

device_combo = ttk.Combobox(root, values=device_names)
state_combo = ttk.Combobox(root, values=states)
site_combo = ttk.Combobox(root, values=sites)
device_listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, height=5)
for d in device_names:
    device_listbox.insert(tk.END, d)

# Submit button
tk.Button(root, text="Run Task", command=perform_task).grid(row=6, column=0, columnspan=2, pady=10)

update_scope_inputs()
root.mainloop()
