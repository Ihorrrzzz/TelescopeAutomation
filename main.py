import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from calibration import set_calibration
from uploader import upload_calibrated_files
from auth import get_auth_token
from login import login_window, save_credentials, delete_credentials

# Global variables for authentication and calibration
token = ""
app = None
calibrated_lights = None
lights = None
oname = ""  # Variable for ONAME (determined by camera selection)

# Main application class
class CalibrationApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Telescope Automation")
        self.frame = tk.Frame(self.master)
        self.frame.pack(pady=20, padx=20)

        # Observatory Selection
        # observatory_label = tk.Label(self.frame, text="Observatory: Lisnyky Observatory AZT-8 70-cm")
        # observatory_label.pack(side=tk.TOP, padx=10, pady=5)

        observatory_label = tk.Label(self.frame, text="Select Observatory:")
        observatory_label.pack(side=tk.TOP, padx=10, pady=5)

        observatory_combo = ttk.Combobox(self.frame, values=["Lisnyky Observatory AZT-8 70-cm"], state="readonly")
        observatory_combo.pack(side=tk.TOP, padx=10, pady=5)

        # Camera Selection Dropdown
        camera_label = tk.Label(self.frame, text="Select Camera:")
        camera_label.pack(side=tk.TOP, padx=10, pady=5)

        self.camera_combo = ttk.Combobox(self.frame, values=["FLI PL47-10", "Moravian C4-16000"], state="readonly")
        self.camera_combo.pack(side=tk.TOP, padx=10, pady=5)
        self.camera_combo.bind("<<ComboboxSelected>>", self.handle_camera_selection)

        # Button to start calibration process
        self.calibration_button = tk.Button(self.frame, text="Calibration", command=self.set_calibration)
        self.calibration_button.pack(padx=10, pady=20)

        # Button for uploading the calibrated files
        self.upload_button = tk.Button(self.frame, text="Bulk Upload", command=self.upload_calibrated_files)
        self.upload_button.pack(padx=10, pady=20)
        # self.upload_button.config(state=tk.DISABLED)  # Disabled until calibration is complete

        # Logout button
        self.logout_button = tk.Button(self.frame, text="Logout", command=self.logout, fg="red")
        self.logout_button.pack(padx=10, pady=20)

    def handle_camera_selection(self, event):
        global oname
        camera = self.camera_combo.get()

        if camera == "FLI PL47-10":
            oname = "AZT-8_PL-4710"
        elif camera == "Moravian C4-16000":
            oname = "AZT-8_C4-16000"
        else:
            oname = ""  # Just in case no camera is selected, but this shouldn't happen

    def logout(self):
        delete_credentials()  # Delete stored credentials
        self.master.destroy()  # Close the main window
        login_window(handle_login)  # Reopen the login window

    def set_calibration(self):
        global calibrated_lights, lights
        calibrated_lights, lights = set_calibration()

        if calibrated_lights and lights:
            self.upload_button.config(state=tk.NORMAL)  # Enable the upload button after calibration is done

    def upload_calibrated_files(self):
        global token, lights, oname
        if not oname:
            messagebox.showerror("Error", "Please select a camera before uploading.")
            return

        folder_selected = filedialog.askdirectory(title="Select Folder Containing Calibrated Files")
        if not folder_selected:
            return

        calibrated_files = [os.path.join(folder_selected, file) for file in os.listdir(folder_selected)
                            if file.endswith(('.fit', '.fits'))]
        if not calibrated_files:
            messagebox.showerror("Error", "No calibrated files found in the selected folder.")
            return

        target_name = self.ask_target_name()
        if not target_name:
            return

        try:
            upload_calibrated_files(calibrated_files, token, target_name, oname, self.master)
        except Exception as e:
            messagebox.showerror("Error", f"Error uploading calibrated files: {e}")
            print(f"Error uploading calibrated files: {e}")

    def ask_target_name(self):
        target_name_window = tk.Toplevel(self.master)
        target_name_window.title("Enter Target Name")

        tk.Label(target_name_window, text="Target Name").pack(pady=5)
        target_name_entry = tk.Entry(target_name_window)
        target_name_entry.pack(pady=5)

        submit_button = tk.Button(target_name_window, text="Submit",
                                  command=lambda: target_name_window.quit())
        submit_button.pack(pady=20)

        target_name_window.mainloop()
        target_name = target_name_entry.get().strip()
        target_name_window.destroy()

        if not target_name:
            messagebox.showerror("Error", "Target name cannot be empty.")
            return None

        return target_name


# Function to handle login and open main window
def handle_login(username, password, root):
    global token
    try:
        token = get_auth_token(username, password)
        print("Successfully logged in")
        root.destroy()  # Close the login window
        save_credentials(username, password)
        create_main_window()  # Open the main window
    except Exception as e:
        print(f"Login failed: {e}")
        tk.messagebox.showerror("Login Failed", "Invalid credentials. Please try again.")


# Create main window after login
def create_main_window():
    global app
    root = tk.Tk()
    app = CalibrationApp(root)
    root.mainloop()


# Start the login process
login_window(handle_login)
