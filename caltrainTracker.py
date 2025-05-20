import requests
import pandas as pd
import pytz
import datetime
import json
import tkinter as tk
from tkinter import ttk
from geopy.distance import geodesic
from tzlocal import get_localzone
import threading
import time
from PIL import Image, ImageTk
import os
import pygame
import random
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_time_zone():
    try:
        tz = get_localzone()
    except Exception:
        tz = datetime.datetime.now().astimezone().tzinfo
    print(f"LOCAL TIME ZONE: {tz}")
    return tz

def ping_train():
    response = requests.get(url)
    if response.status_code == 200:
        decoded_content = response.content.decode("utf-8-sig")
        data = json.loads(decoded_content)
    else:
        return False
    
    if data["Siri"]["ServiceDelivery"]["VehicleMonitoringDelivery"].get("VehicleActivity") is None:
        return False
    else:
        return data

def create_caltrain_dfs(data: dict) -> pd.DataFrame:
    trains = []
    for train in data["Siri"]["ServiceDelivery"]["VehicleMonitoringDelivery"]["VehicleActivity"]:
        train_obj = train["MonitoredVehicleJourney"]

        if train_obj.get("OnwardCalls") is None:
            continue

        next_stop_df = pd.DataFrame(
            [
                [
                    train_obj["MonitoredCall"]["StopPointName"],
                    train_obj["MonitoredCall"]["StopPointRef"],
                    train_obj["MonitoredCall"]["AimedArrivalTime"],
                    train_obj["MonitoredCall"]["ExpectedArrivalTime"],
                ]
            ],
            columns=["stop_name", "stop_id", "aimed_arrival_time", "expected_arrival_time"],
        )
        destinations_df = pd.DataFrame(
            [
                [
                    stop["StopPointName"],
                    stop["StopPointRef"],
                    stop["AimedArrivalTime"],
                    stop["ExpectedArrivalTime"],
                ]
                for stop in train_obj["OnwardCalls"]["OnwardCall"]
            ],
            columns=["stop_name", "stop_id", "aimed_arrival_time", "expected_arrival_time"],
        )
        destinations_df = pd.concat([next_stop_df, destinations_df])
        destinations_df["origin"] = train_obj["OriginName"]
        destinations_df["origin_id"] = train_obj["OriginRef"]
        destinations_df["direction"] = train_obj["DirectionRef"] + "B"
        destinations_df["line_type"] = train_obj["PublishedLineName"]
        destinations_df["destination"] = train_obj["DestinationName"]

        destinations_df = destinations_df[
            [
                "origin",
                "origin_id",
                "direction",
                "line_type",
                "destination",
                "stop_name",
                "stop_id",
                "aimed_arrival_time",
                "expected_arrival_time"
            ]
        ]
        destinations_df["stops_away"] = destinations_df.index
        trains.append(destinations_df)
    trains_df = pd.concat(trains)

    trains_df["aimed_arrival_time"] = pd.to_datetime(trains_df["aimed_arrival_time"]).dt.tz_convert(LOCAL_TZ)
    trains_df["expected_arrival_time"] = pd.to_datetime(trains_df["expected_arrival_time"]).dt.tz_convert(LOCAL_TZ)
    trains_df["stop_id"] = trains_df["stop_id"].astype(float)
    trains_df["origin_id"] = trains_df["origin_id"].astype(float)

    stop_ids = pd.read_csv("stop_ids.csv")

    sb_trains_df = pd.merge(trains_df, stop_ids, left_on="stop_id", right_on="stop1", how="inner")
    nb_trains_df = pd.merge(trains_df, stop_ids, left_on="stop_id", right_on="stop2", how="inner")
    trains_df = pd.concat([sb_trains_df, nb_trains_df])

    trains_df["Departure Time"] = trains_df["expected_arrival_time"]
    trains_df["Current Time"] = datetime.datetime.now(LOCAL_TZ)
    trains_df["ETA"] = trains_df["Departure Time"] - trains_df["Current Time"]
    trains_df["Direction"] = trains_df["direction"]
    return trains_df

class CaltrainTracker(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Caltrain Tracker")
        self.geometry("800x400")
        self.configure(bg='#2C3E50')  # Dark blue background

        # Initialize pygame for sound
        pygame.mixer.init()

        # Add control flag for the update loop
        self.running = True
        self.force_update = False
        self.sound_enabled = True
        self.last_alert_time = None

        # Load stations data
        self.stations_df = pd.read_csv("stop_ids.csv")
        self.stations = self.stations_df['stopname'].tolist()
        
        # Initialize selected stations
        self.from_station = tk.StringVar(value="Palo Alto")
        self.to_station = tk.StringVar(value="San Francisco")

        # Configure styles
        self.configure_styles()

        # Load and set background image
        try:
            self.bg_image = Image.open(os.path.join("assets", "background.png"))
            # Resize background to fit window while maintaining aspect ratio
            bg_width, bg_height = self.bg_image.size
            window_ratio = 800/400
            bg_ratio = bg_width/bg_height
            
            if bg_ratio > window_ratio:
                new_width = 800
                new_height = int(800/bg_ratio)
            else:
                new_height = 400
                new_width = int(400*bg_ratio)
                
            self.bg_image = self.bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.bg_photo = ImageTk.PhotoImage(self.bg_image)
            self.bg_label = tk.Label(self, image=self.bg_photo)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        except Exception as e:
            print(f"Could not load background image: {e}")

        # Load train sprites
        self.sprites = []
        try:
            for i in range(1, 3):
                sprite = Image.open(os.path.join("assets", f"sprite{i}.png"))
                sprite = sprite.resize((80, 80), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(sprite)
                self.sprites.append(photo)
        except Exception as e:
            print(f"Could not load train sprites: {e}")

        # Create main frame with padding
        self.main_frame = ttk.Frame(self, style='Card.TFrame')
        self.main_frame.place(relx=0.5, rely=0.5, anchor='center', width=300, height=250)

        # Station selection frame
        station_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        station_frame.pack(fill='x', pady=(0, 5))

        # From station dropdown
        ttk.Label(
            station_frame, 
            text="From:", 
            style='Label.TLabel'
        ).pack(side='left', padx=2)
        
        self.from_dropdown = ttk.Combobox(
            station_frame, 
            textvariable=self.from_station,
            values=self.stations,
            state='readonly',
            width=15,
            style='Custom.TCombobox'
        )
        self.from_dropdown.pack(side='left', padx=2)

        # To station dropdown
        ttk.Label(
            station_frame, 
            text="To:", 
            style='Label.TLabel'
        ).pack(side='left', padx=2)
        
        self.to_dropdown = ttk.Combobox(
            station_frame, 
            textvariable=self.to_station,
            values=self.stations,
            state='readonly',
            width=15,
            style='Custom.TCombobox'
        )
        self.to_dropdown.pack(side='left', padx=2)

        # Title with custom styling
        title_label = ttk.Label(
            self.main_frame,
            text="Upcoming Arrivals",
            font=('Helvetica', 12, 'bold'),
            justify='center',
            style='Title.TLabel'
        )
        title_label.pack(pady=(0, 5))

        # Sound alert toggle
        self.sound_var = tk.BooleanVar(value=False)
        self.sound_check = ttk.Checkbutton(
            self.main_frame,
            text="Sound Alert",
            variable=self.sound_var,
            style='Custom.TCheckbutton'
        )
        self.sound_check.pack(pady=(0, 5))

        # Create Treeview with custom styling
        self.tree = ttk.Treeview(
            self.main_frame,
            columns=('Time', 'ETA', 'Direction', 'Type'),
            show='headings',
            height=4,
            style='Custom.Treeview'
        )

        # Configure columns
        self.tree.heading('Time', text='Time')
        self.tree.heading('ETA', text='ETA (mm:ss)')
        self.tree.heading('Direction', text='Dir')
        self.tree.heading('Type', text='Type')
        
        self.tree.column('Time', width=100)
        self.tree.column('ETA', width=70)
        self.tree.column('Direction', width=40)
        self.tree.column('Type', width=60)

        self.tree.pack(fill='both', expand=True)

        # Add train sprites to the top corners
        if self.sprites:
            self.left_sprite = tk.Label(self, image=self.sprites[0], bg='#2C3E50')
            self.left_sprite.place(relx=0.1, rely=0.4, anchor='nw')
            
            self.right_sprite = tk.Label(self, image=self.sprites[1], bg='#2C3E50')
            self.right_sprite.place(relx=0.9, rely=0.4, anchor='ne')

        # Bind window resize event to update sprite positions
        self.bind('<Configure>', self.on_window_resize)

        # Restore automatic station change binding
        self.from_dropdown.bind('<<ComboboxSelected>>', self.on_station_change)
        self.to_dropdown.bind('<<ComboboxSelected>>', self.on_station_change)

        # Start update thread
        self.update_thread = threading.Thread(target=self.update_data, daemon=True)
        self.update_thread.start()

    def configure_styles(self):
        """Configure custom styles for the application"""
        style = ttk.Style()
        
        # Configure the card frame style
        style.configure(
            'Card.TFrame',
            background='#FFFFFF',
            relief='solid',
            borderwidth=1
        )
        
        # Configure label styles
        style.configure(
            'Label.TLabel',
            background='#FFFFFF',
            foreground='#2C3E50',
            font=('Helvetica', 10)
        )
        
        # Configure title style
        style.configure(
            'Title.TLabel',
            background='#FFFFFF',
            foreground='#2C3E50',
            font=('Helvetica', 12, 'bold')
        )
        
        # Configure combobox style
        style.configure(
            'Custom.TCombobox',
            background='#FFFFFF',
            fieldbackground='#FFFFFF',
            foreground='#2C3E50',
            arrowcolor='#2C3E50',
            selectbackground='#3498DB',
            selectforeground='#FFFFFF'
        )
        
        # Configure treeview style
        style.configure(
            'Custom.Treeview',
            background='#FFFFFF',
            foreground='#2C3E50',
            fieldbackground='#FFFFFF',
            rowheight=25,
            font=('Helvetica', 10)
        )
        
        # Configure treeview heading style
        style.configure(
            'Custom.Treeview.Heading',
            background='#2C3E50',
            foreground='#000000',
            font=('Helvetica', 10, 'bold'),
            relief='flat'
        )
        
        # Configure treeview selected style
        style.map(
            'Custom.Treeview',
            background=[('selected', '#3498DB')],
            foreground=[('selected', '#FFFFFF')]
        )
        
        # Configure treeview heading hover style
        style.map(
            'Custom.Treeview.Heading',
            background=[('active', '#34495E')],
            foreground=[('active', '#000000')]
        )

        # Configure checkbox style
        style.configure(
            'Custom.TCheckbutton',
            background='#FFFFFF',
            foreground='#2C3E50'
        )

    def get_train_direction(self, from_stop, to_stop):
        """Determine if the train should be northbound or southbound based on station order"""
        from_nb_id = from_stop['stop1'].iloc[0]
        to_nb_id = to_stop['stop1'].iloc[0]
        return 'NB' if from_nb_id > to_nb_id else 'SB'

    def get_train_type(self, line_type):
        """Determine train type from line type"""
        if 'BABY BULLET' in line_type.upper():
            return 'BB'
        elif 'LIMITED' in line_type.upper():
            return 'LIM'
        else:
            return 'LOC'

    def play_alert_sound(self):
        """Play train sound for approaching train"""
        if self.sound_var.get():
            try:
                # Load and play the train sound
                pygame.mixer.music.load(os.path.join("assets", "train_noises.wav"))
                pygame.mixer.music.play()
            except Exception as e:
                print(f"Could not play train sound: {e}")

    def on_station_change(self, event=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.force_update = True

    def on_window_resize(self, event):
        if hasattr(self, 'left_sprite') and hasattr(self, 'right_sprite'):
            self.left_sprite.place(relx=0.1, rely=0.4, anchor='nw')
            self.right_sprite.place(relx=0.9, rely=0.4, anchor='ne')

    def update_data(self):
        while self.running:
            try:
                if self.force_update or not hasattr(self, 'last_update') or (datetime.datetime.now() - self.last_update).total_seconds() >= 5:
                    data = ping_train()
                    
                    if data:
                        caltrain_data = create_caltrain_dfs(data)
                        
                        from_stop = self.stations_df[self.stations_df['stopname'] == self.from_station.get()]
                        to_stop = self.stations_df[self.stations_df['stopname'] == self.to_station.get()]
                        
                        if not from_stop.empty and not to_stop.empty:
                            required_direction = self.get_train_direction(from_stop, to_stop)
                            direction_filtered = caltrain_data[caltrain_data['direction'].str.contains(required_direction)]
                            
                            if not direction_filtered.empty:
                                from_stop_id = from_stop['stop1'].iloc[0] if required_direction == 'NB' else from_stop['stop2'].iloc[0]
                                
                                upcoming = (
                                    direction_filtered
                                    .loc[direction_filtered["stop_id"] == from_stop_id,
                                         "expected_arrival_time"]
                                    .sort_values()
                                    .head(5)
                                )

                                for item in self.tree.get_children():
                                    self.tree.delete(item)

                                now = datetime.datetime.now(upcoming.iloc[0].tzinfo)
                                for t in upcoming:
                                    eta_total = int((t - now).total_seconds())
                                    eta_min, eta_sec = divmod(max(eta_total, 0), 60)
                                    eta_str = f"{eta_min:02d}:{eta_sec:02d}"
                                    
                                    if eta_min < 10:
                                        tag = 'red'
                                    elif eta_min < 20:
                                        tag = 'yellow'
                                    else:
                                        tag = 'green'

                                    train_direction = direction_filtered.loc[direction_filtered['expected_arrival_time'] == t, 'direction'].iloc[0]
                                    direction_str = 'NB' if 'NB' in train_direction else 'SB'
                                    
                                    # Get train type
                                    train_type = self.get_train_type(
                                        direction_filtered.loc[direction_filtered['expected_arrival_time'] == t, 'line_type'].iloc[0]
                                    )

                                    self.tree.insert('', 'end', 
                                        values=(
                                            t.strftime('%I:%M:%S %p'),
                                            eta_str,
                                            direction_str,
                                            train_type
                                        ),
                                        tags=(tag,)
                                    )

                                    # Play sound 
                                    # alert for trains arriving in less than 8 minutes
                                    if eta_min < 8 and self.sound_var.get():
                                        
                                        if not self.last_alert_time or (datetime.datetime.now() - self.last_alert_time).total_seconds() > 60*8:
                                            self.play_alert_sound()
                                            self.last_alert_time = datetime.datetime.now()

                                # Configure tags with colored backgrounds
                                self.tree.tag_configure('red', background='#FFE5E5')
                                self.tree.tag_configure('yellow', background='#FFF8E5')
                                self.tree.tag_configure('green', background='#E5FFE5')

                    self.force_update = False
                    self.last_update = datetime.datetime.now()

            except Exception as e:
                print(f"Error updating data: {e}")

            time.sleep(1)

    def on_closing(self):
        """Handle window closing"""
        self.running = False
        self.destroy()

if __name__ == "__main__":
    API_KEY = os.getenv('CALTRAIN_API_KEY')
    if not API_KEY:
        print("Error: CALTRAIN_API_KEY not found in environment variables")
        print("Please create a .env file with your API key")
        print("Example: CALTRAIN_API_KEY=your_api_key_here")
        exit(1)
        
    url = f"https://api.511.org/transit/VehicleMonitoring?api_key={API_KEY}&agency=CT"
    LOCAL_TZ = get_time_zone()
    
    app = CaltrainTracker()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
        